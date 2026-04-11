"""
Web interface module for ZotGrep.

Provides a localhost Flask web GUI for searching Zotero libraries and editing
persistent user settings.
Launch with: zotgrep --web
"""

import re
import tempfile
from datetime import datetime
from typing import Any, Dict

from flask import Flask, redirect, render_template_string, request, send_file, url_for

from .config import (
    ZotGrepConfig,
    get_config,
    get_user_config_path,
    load_config_from_file,
    save_config_to_file,
)
from .result_handler import ResultHandler
from .search_engine import ZoteroSearchEngine
from .text_analyzer import metadata_query_uses_unsupported_operators, parse_full_text_query
from .version import get_runtime_version

# Module-level storage for last search results (single-user localhost app)
_last_search: Dict[str, Any] = {}


def _highlight_filter(text: str) -> str:
    """Convert ***term*** markers to <mark> tags for HTML display."""
    if not text:
        return ""
    return re.sub(r"\*\*\*(.*?)\*\*\*", r"<mark>\1</mark>", text)


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_search_form(config: ZotGrepConfig) -> Dict[str, Any]:
    return {
        "zotero_query": "",
        "fulltext_terms": "",
        "metadata_only": False,
        "include_abstract": True,
        "publication_filter": "",
        "item_type_filter": ", ".join(config.item_type_filter or []),
        "collection_filter": config.collection_filter or "",
        "tag_filter": ", ".join(config.tag_filter or []),
        "tag_match_mode": config.tag_match_mode,
        "metadata_search_mode": config.metadata_search_mode,
        "max_results": config.max_results_stage1,
        "context_window": config.context_sentence_window,
    }


def _build_settings_form(config: ZotGrepConfig) -> Dict[str, Any]:
    return {
        "zotero_user_id": config.zotero_user_id,
        "zotero_api_key": config.zotero_api_key,
        "library_type": config.library_type,
        "base_attachment_path": config.base_attachment_path,
        "max_results_stage1": config.max_results_stage1,
        "context_sentence_window": config.context_sentence_window,
    }


def _group_results_for_display(
    results: Any,
    fulltext_terms: list[str] | None = None,
) -> list[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for result in results or []:
        reference_key = result.get("reference_key") or result.get("reference_title") or "unknown"
        if reference_key not in grouped:
            grouped[reference_key] = {
                "reference_title": result.get("reference_title", "N/A"),
                "authors": result.get("authors", "N/A"),
                "publication_year": result.get("publication_year", "N/A"),
                "publication_title": result.get("publication_title", "N/A"),
                "doi": result.get("doi", ""),
                "abstract": result.get("abstract", ""),
                "reference_key": result.get("reference_key", ""),
                "zotero_item_url": result.get("zotero_item_url", ""),
                "term_counts": {term: 0 for term in (fulltext_terms or []) if term},
                "hits": [],
            }

        has_hit = bool(
            result.get("search_term_found")
            or result.get("context")
            or result.get("zotero_pdf_url")
        )
        if not has_hit:
            continue

        parsed_terms = [
            term.strip()
            for term in str(result.get("search_term_found", "")).split(",")
            if term.strip()
        ]
        for term in parsed_terms:
            current_count = grouped[reference_key]["term_counts"].get(term, 0)
            grouped[reference_key]["term_counts"][term] = current_count + 1

        grouped[reference_key]["hits"].append(
            {
                "pdf_filename": result.get("pdf_filename", ""),
                "page_number": result.get("page_number", ""),
                "search_term_found": result.get("search_term_found", ""),
                "context_highlighted": result.get("context_highlighted", ""),
                "zotero_pdf_url": result.get("zotero_pdf_url", ""),
            }
        )

    grouped_results = list(grouped.values())
    for group in grouped_results:
        for index, hit in enumerate(group["hits"], start=1):
            hit["occurrence_label"] = f"Occurrence #{index}"
            hit["is_initially_visible"] = index <= 10
        group["term_counts"] = [
            {"term": term, "count": count}
            for term, count in group["term_counts"].items()
        ]
        group["hidden_hit_count"] = max(0, len(group["hits"]) - 10)
        group["show_expand_button"] = group["hidden_hit_count"] > 0
    return grouped_results


def _render_page(content_template: str, **context: Any) -> str:
    template = BASE_TEMPLATE.replace("__PAGE_CONTENT__", content_template)
    return render_template_string(template, app_version=get_runtime_version(), **context)


def _render_search_page(
    config: ZotGrepConfig,
    form: Dict[str, Any],
    results: Any = None,
    error: str | None = None,
    success: str | None = None,
    summary: str | None = None,
    warnings: list[str] | None = None,
    fulltext_terms: list[str] | None = None,
) -> str:
    return _render_page(
        SEARCH_CONTENT_TEMPLATE,
        active_page="search",
        page_title="Search",
        config=config,
        form=form,
        results=results,
        error=error,
        success=success,
        summary=summary,
        warnings=warnings or [],
        grouped_results=_group_results_for_display(results, fulltext_terms=fulltext_terms),
    )


def _render_settings_page(
    form: Dict[str, Any],
    error: str | None = None,
    success: str | None = None,
) -> str:
    return _render_page(
        SETTINGS_CONTENT_TEMPLATE,
        active_page="settings",
        page_title="General Settings",
        form=form,
        error=error,
        success=success,
        config_path=get_user_config_path(),
    )


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = "zotgrep-local"
    app.jinja_env.filters["highlight"] = _highlight_filter

    @app.route("/")
    def index():
        config = get_config()
        return _render_search_page(
            config=config,
            form=_build_search_form(config),
            fulltext_terms=[],
        )

    @app.route("/search", methods=["POST"])
    def search():
        config = get_config()

        zotero_query = request.form.get("zotero_query", "").strip()
        fulltext_str = request.form.get("fulltext_terms", "").strip()
        metadata_only = "metadata_only" in request.form
        include_abstract = "include_abstract" in request.form
        publication_filter = request.form.get("publication_filter", "").strip()
        item_type_filter = request.form.get("item_type_filter", "").strip()
        collection_filter = request.form.get("collection_filter", "").strip()
        tag_filter = request.form.get("tag_filter", "").strip()
        tag_match_mode = request.form.get("tag_match_mode", config.tag_match_mode).strip().lower() or "all"
        if tag_match_mode not in {"all", "any"}:
            tag_match_mode = "all"
        metadata_search_mode = request.form.get(
            "metadata_search_mode", config.metadata_search_mode
        ).strip()
        if metadata_search_mode not in {"titleCreatorYear", "everything"}:
            metadata_search_mode = "titleCreatorYear"
        max_results = request.form.get("max_results", str(config.max_results_stage1))
        context_window = request.form.get(
            "context_window",
            str(config.context_sentence_window),
        )

        form = {
            "zotero_query": zotero_query,
            "fulltext_terms": fulltext_str,
            "metadata_only": metadata_only,
            "include_abstract": include_abstract,
            "publication_filter": publication_filter,
            "item_type_filter": item_type_filter,
            "collection_filter": collection_filter,
            "tag_filter": tag_filter,
            "tag_match_mode": tag_match_mode,
            "metadata_search_mode": metadata_search_mode,
            "max_results": max_results,
            "context_window": context_window,
        }

        if not zotero_query:
            return _render_search_page(
                config=config,
                form=form,
                error="Zotero metadata search terms are required.",
                fulltext_terms=[],
            )

        config.max_results_stage1 = _parse_int(max_results, config.max_results_stage1)
        config.context_sentence_window = _parse_int(
            context_window,
            config.context_sentence_window,
        )

        if publication_filter:
            config.publication_title_filter = [
                value.strip()
                for value in publication_filter.split(",")
                if value.strip()
            ]
        else:
            config.publication_title_filter = None

        config.item_type_filter = [
            value.strip()
            for value in item_type_filter.split(",")
            if value.strip()
        ] or None
        config.collection_filter = collection_filter or None
        config.tag_filter = [
            value.strip()
            for value in tag_filter.split(",")
            if value.strip()
        ] or None
        config.tag_match_mode = tag_match_mode
        config.metadata_search_mode = metadata_search_mode

        warnings: list[str] = []
        if metadata_query_uses_unsupported_operators(zotero_query):
            warnings.append(
                "Metadata search still uses Zotero quick-search semantics. '*', 'AND', and "
                "'OR' are passed through unchanged and are not interpreted as operators by ZotGrep."
            )

        fulltext_terms: list[str] = []
        if fulltext_str:
            try:
                fulltext_terms = parse_full_text_query(fulltext_str).leaf_terms
            except ValueError as exc:
                return _render_search_page(
                    config=config,
                    form=form,
                    error=f"Invalid full-text query: {exc}",
                    warnings=warnings,
                    fulltext_terms=[],
                )

        engine = ZoteroSearchEngine(config)
        if not engine.connect_to_zotero():
            return _render_search_page(
                config=config,
                form=form,
                error=(
                    "Failed to connect to Zotero. Make sure Zotero is running "
                    "with the local API enabled."
                ),
                warnings=warnings,
                fulltext_terms=fulltext_terms,
            )

        try:
            results = engine.search_zotero_and_full_text(
                zotero_query,
                fulltext_str,
                include_abstract=include_abstract,
                metadata_only=metadata_only,
            )
        except Exception as exc:
            return _render_search_page(
                config=config,
                form=form,
                error=f"Search error: {exc}",
                warnings=[*warnings, *engine.warnings],
                fulltext_terms=fulltext_terms,
            )

        _last_search.update(
            {
                "results": results,
                "zotero_query": zotero_query,
                "fulltext_terms": fulltext_terms,
                "include_abstract": include_abstract,
                "context_window": config.context_sentence_window,
                "metadata_filters": engine.get_metadata_filters_for_output(),
            }
        )

        summary = engine.get_search_summary(results) if results else "No results found."
        return _render_search_page(
            config=config,
            form=form,
            results=results,
            summary=summary,
            warnings=[*warnings, *engine.warnings],
            fulltext_terms=fulltext_terms,
        )

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "GET":
            return _render_settings_page(_build_settings_form(load_config_from_file()))

        form = {
            "zotero_user_id": request.form.get("zotero_user_id", "").strip(),
            "zotero_api_key": request.form.get("zotero_api_key", "").strip(),
            "library_type": request.form.get("library_type", "user").strip() or "user",
            "base_attachment_path": request.form.get("base_attachment_path", "").strip(),
            "max_results_stage1": request.form.get("max_results_stage1", "100").strip(),
            "context_sentence_window": request.form.get("context_sentence_window", "2").strip(),
        }

        try:
            config = ZotGrepConfig(
                zotero_user_id=form["zotero_user_id"] or "0",
                zotero_api_key=form["zotero_api_key"] or "local",
                library_type=form["library_type"],
                base_attachment_path=form["base_attachment_path"],
                max_results_stage1=_parse_int(form["max_results_stage1"], 100),
                context_sentence_window=_parse_int(form["context_sentence_window"], 2),
                publication_title_filter=None,
                debug_publication_filter=False,
                use_local_api=True,
            )
            saved_path = save_config_to_file(config)
        except ValueError as exc:
            return _render_settings_page(form=form, error=f"Settings error: {exc}")
        except OSError as exc:
            return _render_settings_page(form=form, error=f"Could not save settings: {exc}")

        return _render_settings_page(
            form=_build_settings_form(config),
            success=f"Saved settings to {saved_path}",
        )

    @app.route("/export/<fmt>")
    def export(fmt):
        if not _last_search.get("results"):
            return redirect(url_for("index"))

        results = _last_search["results"]
        zotero_query = _last_search.get("zotero_query")
        fulltext_terms = _last_search.get("fulltext_terms")
        include_abstract = _last_search.get("include_abstract", True)
        context_window = _last_search.get("context_window", 2)
        metadata_filters = _last_search.get("metadata_filters")

        handler = ResultHandler()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if fmt == "csv":
            path = tempfile.mktemp(suffix=".csv")
            handler.save_results_to_csv(results, path, include_abstract=include_abstract)
            return send_file(
                path,
                as_attachment=True,
                download_name=f"zotgrep_results_{timestamp}.csv",
                mimetype="text/csv",
            )
        if fmt == "json":
            path = tempfile.mktemp(suffix=".json")
            handler.save_results_to_json(
                results,
                path,
                zotero_query=zotero_query,
                full_text_query=fulltext_terms,
                include_abstract=include_abstract,
                context_window=context_window,
                metadata_filters=metadata_filters,
            )
            return send_file(
                path,
                as_attachment=True,
                download_name=f"zotgrep_results_{timestamp}.json",
                mimetype="application/json",
            )
        if fmt == "md":
            path = tempfile.mktemp(suffix=".md")
            handler.save_results_to_markdown(
                results,
                path,
                zotero_query=zotero_query,
                full_text_query=fulltext_terms,
                include_abstract=include_abstract,
                context_window=context_window,
                metadata_filters=metadata_filters,
            )
            return send_file(
                path,
                as_attachment=True,
                download_name=f"zotgrep_results_{timestamp}.md",
                mimetype="text/markdown",
            )
        return redirect(url_for("index"))

    return app


BASE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="mocha">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZotGrep · {{ page_title }}</title>
<style>
  [data-theme="latte"] {
    --bg: #eff1f5;
    --card-bg: #e6e9ef;
    --input-bg: #eff1f5;
    --border: #bcc0cc;
    --primary: #1d3557;
    --primary-hover: #457b9d;
    --text: #243447;
    --text-muted: #5c6773;
    --danger: #b42318;
    --danger-bg: #fef3f2;
    --success: #067647;
    --success-bg: #ecfdf3;
    --mark-bg: rgba(230, 126, 34, 0.18);
    --context-bg: #dce0e8;
    --overlay-bg: rgba(239,241,245,0.9);
    --header-accent: #1d3557;
    --btn-text: #f8fafc;
    --advanced-bg: #dce0e8;
    --placeholder: #8c8fa1;
  }

  [data-theme="solarized"] {
    --bg: #fdf6e3;
    --card-bg: #eee8d5;
    --input-bg: #e4ddc8;
    --border: #d3cbb7;
    --primary: #005f73;
    --primary-hover: #0a9396;
    --text: #586e75;
    --text-muted: #6d8086;
    --danger: #dc322f;
    --danger-bg: #fce9e7;
    --success: #2a9d8f;
    --success-bg: #e5f5f2;
    --mark-bg: rgba(181,137,0,0.22);
    --context-bg: #e8e1cc;
    --overlay-bg: rgba(253,246,227,0.9);
    --header-accent: #005f73;
    --btn-text: #fdf6e3;
    --advanced-bg: #ddd6c0;
    --placeholder: #93a1a1;
  }

  [data-theme="mocha"] {
    --bg: #1e1e2e;
    --card-bg: #313244;
    --input-bg: #45475a;
    --border: #585b70;
    --primary: #cba6f7;
    --primary-hover: #b4befe;
    --text: #cdd6f4;
    --text-muted: #bac2de;
    --danger: #f38ba8;
    --danger-bg: #45293a;
    --success: #94e2d5;
    --success-bg: #244546;
    --mark-bg: rgba(249,226,175,0.45);
    --mark-text: #1e1e2e;
    --context-bg: #45475a;
    --overlay-bg: rgba(30,30,46,0.9);
    --header-accent: #cba6f7;
    --btn-text: #1e1e2e;
    --advanced-bg: #313244;
    --placeholder: #7f849c;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family:
      -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      Roboto,
      Ubuntu,
      Cantarell,
      "Noto Sans",
      "Helvetica Neue",
      Arial,
      sans-serif;
    background:
      radial-gradient(circle at top right, rgba(69,123,157,0.12), transparent 28%),
      radial-gradient(circle at left center, rgba(244,162,97,0.14), transparent 24%),
      var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
  }
  .container { max-width: 1040px; margin: 0 auto; padding: 0 1.5rem; }
  header {
    border-bottom: 2px solid var(--header-accent);
    padding: 0.9rem 0;
    margin-bottom: 1.5rem;
    backdrop-filter: blur(8px);
  }
  header .container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .header-left {
    display: flex;
    align-items: baseline;
    gap: 0.65rem;
  }
  header h1 {
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--header-accent);
  }
  .version {
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .header-right {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    flex-wrap: wrap;
  }
  .nav-links {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .nav-link {
    text-decoration: none;
    color: var(--text);
    border: 1px solid var(--border);
    background: var(--card-bg);
    padding: 0.45rem 0.85rem;
    border-radius: 999px;
    font-size: 0.86rem;
  }
  .nav-link.active {
    background: var(--primary);
    color: var(--btn-text);
    border-color: var(--primary);
  }
  .theme-switcher {
    display: flex;
    gap: 0.35rem;
    align-items: center;
  }
  .theme-switcher button {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 2px solid var(--border);
    cursor: pointer;
    transition: border-color 0.15s, transform 0.15s;
    padding: 0;
  }
  .theme-switcher button:hover { transform: scale(1.12); }
  .theme-switcher button.active { border-color: var(--header-accent); transform: scale(1.12); }
  .theme-switcher button[data-set-theme="mocha"] { background: linear-gradient(135deg, #1e1e2e 50%, #cba6f7 50%); }
  .theme-switcher button[data-set-theme="latte"] { background: linear-gradient(135deg, #eff1f5 50%, #1d3557 50%); }
  .theme-switcher button[data-set-theme="solarized"] { background: linear-gradient(135deg, #fdf6e3 50%, #005f73 50%); }

  .panel {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.35rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 16px 35px rgba(0,0,0,0.06);
  }
  .panel h2 {
    font-size: 1.1rem;
    margin-bottom: 0.35rem;
  }
  .panel-intro {
    color: var(--text-muted);
    font-size: 0.92rem;
    margin-bottom: 1rem;
  }
  .message {
    border-radius: 10px;
    padding: 0.9rem 1rem;
    margin-bottom: 1rem;
    border: 1px solid transparent;
  }
  .message.error {
    background: var(--danger-bg);
    color: var(--danger);
    border-color: var(--danger);
  }
  .message.warning {
    background: #fffaeb;
    color: #b54708;
    border-color: #f79009;
  }
  .message.success {
    background: var(--success-bg);
    color: var(--success);
    border-color: var(--success);
  }
  .settings-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.8rem;
    margin-bottom: 1rem;
  }
  .mini-card {
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.9rem 1rem;
  }
  .mini-card .label {
    display: block;
    color: var(--text-muted);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
  }
  .mini-card .value {
    font-size: 0.95rem;
    word-break: break-word;
  }
  .form-group { margin-bottom: 1rem; }
  .form-group label {
    display: block;
    font-weight: 600;
    margin-bottom: 0.25rem;
    font-size: 0.9rem;
  }
  .form-group small {
    color: var(--text-muted);
    font-size: 0.8rem;
    display: block;
    margin-top: 0.3rem;
  }
  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group input[type="password"],
  .form-group select {
    width: 100%;
    padding: 0.65rem 0.8rem;
    border: 1px solid var(--border);
    border-radius: 10px;
    font-size: 0.95rem;
    background: var(--input-bg);
    color: var(--text);
  }
  .form-group input:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--primary);
  }
  .form-row-2,
  .form-row-3 {
    display: grid;
    gap: 1rem;
  }
  .form-row-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .form-row-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .checkbox-group {
    display: flex;
    gap: 1.5rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .checkbox-group label {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-weight: 500;
    cursor: pointer;
  }
  .btn-row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.7rem 1.2rem;
    border-radius: 10px;
    font-size: 0.93rem;
    line-height: 1.2;
    min-height: 2.8rem;
    cursor: pointer;
    text-decoration: none;
    font-weight: 600;
    border: none;
  }
  .btn-primary {
    background: var(--primary);
    color: var(--btn-text);
  }
  .btn-primary:hover { background: var(--primary-hover); }
  .btn-outline {
    background: transparent;
    color: var(--primary);
    border: 1px solid var(--primary);
  }
  .btn-outline:hover {
    background: var(--primary);
    color: var(--btn-text);
  }
  .results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    flex-wrap: wrap;
    gap: 0.75rem;
  }
  .export-buttons { display: flex; gap: 0.5rem; flex-wrap: wrap; }
  .result-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.2rem;
    margin-bottom: 1rem;
  }
  .result-card h3 { font-size: 1rem; margin-bottom: 0.4rem; }
  .result-card h3 a { color: var(--primary); text-decoration: none; }
  .result-card h3 a:hover { text-decoration: underline; }
  .result-meta {
    font-size: 0.86rem;
    color: var(--text-muted);
    margin-bottom: 0.55rem;
  }
  .result-meta span { margin-right: 0.9rem; }
  .result-meta a { color: var(--primary); text-decoration: none; }
  .result-context {
    background: var(--context-bg);
    border-left: 3px solid var(--primary);
    padding: 0.8rem 1rem;
    margin-top: 0.75rem;
    font-size: 0.92rem;
    line-height: 1.7;
    border-radius: 0 10px 10px 0;
  }
  .result-context mark {
    background: var(--mark-bg);
    color: var(--mark-text, var(--text));
    padding: 0.1rem 0.2rem;
    border-radius: 2px;
  }
  .pdf-link {
    display: inline-block;
    margin-top: 0.55rem;
    font-size: 0.85rem;
    color: var(--primary);
    text-decoration: none;
  }
  .pdf-link:hover { text-decoration: underline; }
  .term-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1rem;
    margin-bottom: 0.35rem;
  }
  .term-pill {
    display: inline-flex;
    gap: 0.35rem;
    align-items: baseline;
    border: 1px solid var(--border);
    background: var(--input-bg);
    border-radius: 999px;
    padding: 0.35rem 0.7rem;
    font-size: 0.82rem;
  }
  .term-pill .term {
    font-weight: 700;
    color: var(--primary);
  }
  .term-pill .count {
    color: var(--text-muted);
  }
  .hit-list {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.95rem;
  }
  .hit-entry.hidden {
    display: none;
  }
  .hit-entry + .hit-entry {
    border-top: 1px solid var(--border);
    padding-top: 0.95rem;
  }
  .hit-heading {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    align-items: baseline;
    font-size: 0.86rem;
    margin-bottom: 0.55rem;
  }
  .hit-heading .occurrence {
    font-weight: 700;
    color: var(--primary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .hit-heading .page,
  .hit-heading .filename {
    color: var(--text-muted);
  }
  .hit-terms {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 0.45rem;
  }
  .hit-quote {
    margin: 0;
    background: var(--context-bg);
    border-left: 3px solid var(--primary);
    padding: 0.8rem 1rem;
    font-size: 0.92rem;
    line-height: 1.7;
    border-radius: 0 10px 10px 0;
  }
  .hit-quote mark {
    background: var(--mark-bg);
    color: var(--mark-text, var(--text));
    padding: 0.1rem 0.2rem;
    border-radius: 2px;
  }
  .expand-hits-button {
    margin-top: 0.85rem;
  }
  details summary {
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 0.4rem;
  }
  ::placeholder {
    color: var(--placeholder);
    opacity: 1;
  }
  details.advanced-search {
    margin-top: 1rem;
    margin-bottom: 1.25rem;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--advanced-bg);
    padding: 0.2rem 1rem 0.9rem;
  }
  details.advanced-search summary {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
    margin-top: 0;
    padding: 0.7rem 0;
  }
  .advanced-search-body {
    padding-top: 0.3rem;
  }
  details p {
    font-size: 0.85rem;
    margin-top: 0.3rem;
    color: var(--text-muted);
    line-height: 1.5;
  }
  .note {
    color: var(--text-muted);
    font-size: 0.88rem;
  }
  .loading-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: var(--overlay-bg);
    z-index: 1000;
    justify-content: center;
    align-items: center;
    flex-direction: column;
  }
  .loading-overlay.active { display: flex; }
  .spinner {
    width: 42px;
    height: 42px;
    border: 4px solid var(--border);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-overlay p { margin-top: 1rem; color: var(--text-muted); font-size: 0.95rem; }
  .no-results {
    text-align: center;
    padding: 2rem;
    color: var(--text-muted);
  }
  @media (max-width: 800px) {
    .form-row-2, .form-row-3 {
      grid-template-columns: 1fr;
    }
    header .container {
      align-items: flex-start;
    }
  }
</style>
</head>
<body>

<header>
  <div class="container">
    <div class="header-left">
      <h1>ZotGrep</h1>
      <span class="version">v{{ app_version }}</span>
    </div>
    <div class="header-right">
      <nav class="nav-links">
        <a href="/" class="nav-link {{ 'active' if active_page == 'search' else '' }}">Search</a>
        <a href="/settings" class="nav-link {{ 'active' if active_page == 'settings' else '' }}">General Settings</a>
      </nav>
      <div class="theme-switcher">
        <button data-set-theme="mocha" title="Mocha" class="active"></button>
        <button data-set-theme="latte" title="Latte"></button>
        <button data-set-theme="solarized" title="Solarized"></button>
      </div>
    </div>
  </div>
</header>

<main class="container">
__PAGE_CONTENT__
</main>

<div class="loading-overlay" id="loading">
  <div class="spinner"></div>
  <p>Searching... This may take a while for PDF processing.</p>
</div>

<script>
(function() {
  var saved = localStorage.getItem('zotgrep-theme') || 'mocha';
  document.documentElement.setAttribute('data-theme', saved);

  var buttons = document.querySelectorAll('.theme-switcher button');
  function activate(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('zotgrep-theme', theme);
    buttons.forEach(function(button) {
      button.classList.toggle('active', button.getAttribute('data-set-theme') === theme);
    });
  }
  activate(saved);
  buttons.forEach(function(button) {
    button.addEventListener('click', function() {
      activate(button.getAttribute('data-set-theme'));
    });
  });

  document.querySelectorAll('[data-expand-hits]').forEach(function(button) {
    button.addEventListener('click', function() {
      var card = button.closest('.result-card');
      if (!card) {
        return;
      }

      var hiddenHits = card.querySelectorAll('.extra-hit');
      var expanded = button.getAttribute('data-expanded') === 'true';
      hiddenHits.forEach(function(hit) {
        hit.classList.toggle('hidden', expanded);
      });

      if (expanded) {
        button.textContent = 'Show ' + hiddenHits.length + ' more occurrences';
        button.setAttribute('data-expanded', 'false');
      } else {
        button.textContent = 'Show fewer occurrences';
        button.setAttribute('data-expanded', 'true');
      }
    });
  });

  var searchForm = document.getElementById('search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', function() {
      document.getElementById('loading').classList.add('active');
    });
  }
})();
</script>

</body>
</html>
"""


SEARCH_CONTENT_TEMPLATE = r"""
{% if error %}
<div class="message error">{{ error }}</div>
{% endif %}
{% if success %}
<div class="message success">{{ success }}</div>
{% endif %}
{% for warning in warnings %}
<div class="message warning">{{ warning }}</div>
{% endfor %}

<section class="panel">
  <h2>Search Library</h2>
  <p class="panel-intro">
    Search Zotero metadata first, then optionally scan attachment text. Persistent defaults live in General Settings, while the fields below only affect this search.
  </p>

  <form action="/search" method="POST" id="search-form">
    <div class="form-group">
      <label for="zotero_query">Zotero Metadata Search</label>
      <input type="text" id="zotero_query" name="zotero_query"
             value="{{ form.get('zotero_query', '') }}"
             placeholder='e.g. "machine learning health"' required>
    </div>

    <div class="form-group">
      <label for="metadata_search_mode">Metadata Search Scope</label>
      <select id="metadata_search_mode" name="metadata_search_mode">
        <option value="titleCreatorYear" {{ 'selected' if form.get('metadata_search_mode', 'titleCreatorYear') == 'titleCreatorYear' else '' }}>Title, Author &amp; Year</option>
        <option value="everything" {{ 'selected' if form.get('metadata_search_mode') == 'everything' else '' }}>Everything (including Zotero-indexed content)</option>
      </select>
      <small>&#8220;Everything&#8221; searches Zotero&#8217;s indexed attachment text in addition to metadata fields.</small>
    </div>

    <div class="form-group">
      <label for="fulltext_terms">Full-Text Search Terms</label>
      <input type="text" id="fulltext_terms" name="fulltext_terms"
             value="{{ form.get('fulltext_terms', '') }}"
             placeholder="Comma-separated, e.g. algorithm, bias">
      <small>Leave empty for metadata-only search.</small>
    </div>

    {% set advanced_open =
      form.get('publication_filter', '') or
      form.get('item_type_filter', '') or
      form.get('collection_filter', '') or
      form.get('tag_filter', '') or
      form.get('tag_match_mode', 'all') != 'all' or
      form.get('metadata_only') or
      not form.get('include_abstract', True) or
      (form.get('max_results', config.max_results_stage1)|string) != (config.max_results_stage1|string) or
      (form.get('context_window', config.context_sentence_window)|string) != (config.context_sentence_window|string)
    %}
    {# metadata_search_mode is shown outside Advanced, so no need to force-open Advanced for it #}
    <details class="advanced-search" {{ 'open' if advanced_open else '' }}>
      <summary>Advanced Search Settings</summary>
      <div class="advanced-search-body">
        <div class="form-group">
          <label for="publication_filter">Publication Title Filter</label>
          <input type="text" id="publication_filter" name="publication_filter"
                 value="{{ form.get('publication_filter', '') }}"
                 placeholder="Comma-separated publication titles">
        </div>

        <div class="form-row-2">
          <div class="form-group">
            <label for="item_type_filter">Item Type Filter</label>
            <input type="text" id="item_type_filter" name="item_type_filter"
                   value="{{ form.get('item_type_filter', '') }}"
                   placeholder="Comma-separated item types">
          </div>
          <div class="form-group">
            <label for="collection_filter">Collection Filter</label>
            <input type="text" id="collection_filter" name="collection_filter"
                   value="{{ form.get('collection_filter', '') }}"
                   placeholder="Collection key or exact name">
          </div>
        </div>

        <div class="form-row-2">
          <div class="form-group">
            <label for="tag_filter">Tag Filter</label>
            <input type="text" id="tag_filter" name="tag_filter"
                   value="{{ form.get('tag_filter', '') }}"
                   placeholder="Comma-separated Zotero tags">
          </div>
          <div class="form-group">
            <label for="tag_match_mode">Tag Match</label>
            <select id="tag_match_mode" name="tag_match_mode">
              <option value="all" {{ 'selected' if form.get('tag_match_mode', 'all') == 'all' else '' }}>All tags</option>
              <option value="any" {{ 'selected' if form.get('tag_match_mode') == 'any' else '' }}>Any tag</option>
            </select>
          </div>
        </div>

        <div class="form-row-2">
          <div class="form-group">
            <label for="max_results">Max Results</label>
            <input type="number" id="max_results" name="max_results"
                   value="{{ form.get('max_results', config.max_results_stage1) }}" min="1">
          </div>
          <div class="form-group">
            <label for="context_window">Context Window</label>
            <input type="number" id="context_window" name="context_window"
                   value="{{ form.get('context_window', config.context_sentence_window) }}" min="0">
            <small>Sentences before and after a match.</small>
          </div>
        </div>

        <div class="form-group checkbox-group">
          <label>
            <input type="checkbox" name="metadata_only"
                   {{ 'checked' if form.get('metadata_only') else '' }}>
            Metadata only
          </label>
          <label>
            <input type="checkbox" name="include_abstract"
                   {{ 'checked' if form.get('include_abstract', True) else '' }}>
            Include abstracts
          </label>
        </div>
      </div>
    </details>

    <div class="btn-row">
      <button type="submit" class="btn btn-primary">Run Search</button>
      <a href="/settings" class="btn btn-outline">General Settings</a>
    </div>
  </form>
</section>

{% if results is not none %}
  {% if results %}
  <section class="results-header">
    <h2>{{ summary }}</h2>
    <div class="export-buttons">
      <a href="/export/csv" class="btn btn-outline">Export CSV</a>
      <a href="/export/json" class="btn btn-outline">Export JSON</a>
      <a href="/export/md" class="btn btn-outline">Export Markdown</a>
    </div>
  </section>

  {% for paper in grouped_results %}
  <article class="result-card">
    <h3><a href="{{ paper.zotero_item_url }}">{{ paper.reference_title }}</a></h3>
    <div class="result-meta">
      <span>{{ paper.authors }}</span>
      {% if paper.publication_year and paper.publication_year != 'N/A' %}
        <span>({{ paper.publication_year }})</span>
      {% endif %}
      {% if paper.publication_title and paper.publication_title != 'N/A' %}
        <span>{{ paper.publication_title }}</span>
      {% endif %}
      {% if paper.doi %}
        <span><a href="https://doi.org/{{ paper.doi }}" target="_blank">DOI</a></span>
      {% endif %}
    </div>

    {% if paper.abstract %}
    <details>
      <summary>Abstract</summary>
      <p>{{ paper.abstract }}</p>
    </details>
    {% endif %}

    {% if paper.hits %}
    {% if paper.term_counts %}
    <div class="term-summary">
      {% for term_info in paper.term_counts %}
      <span class="term-pill">
        <span class="term">{{ term_info.term }}</span>
        <span class="count">{{ term_info.count }}</span>
      </span>
      {% endfor %}
    </div>
    {% endif %}
    <div class="hit-list">
      {% for hit in paper.hits %}
      <section class="hit-entry {{ '' if hit.is_initially_visible else 'hidden extra-hit' }}">
        <div class="hit-heading">
          <span class="occurrence">{{ hit.occurrence_label }}</span>
          {% if hit.page_number %}
          <span class="page">Page {{ hit.page_number }}</span>
          {% endif %}
          {% if hit.pdf_filename %}
          <span class="filename">{{ hit.pdf_filename }}</span>
          {% endif %}
        </div>
        {% if hit.search_term_found %}
        <div class="hit-terms">Matched terms: {{ hit.search_term_found }}</div>
        {% endif %}
        <blockquote class="hit-quote">
          {{ hit.context_highlighted | highlight | safe }}
        </blockquote>
        <a class="pdf-link" href="{{ hit.zotero_pdf_url }}">
          Open hit in Zotero
        </a>
      </section>
      {% endfor %}
    </div>
    {% if paper.show_expand_button %}
    <button
      type="button"
      class="btn btn-outline expand-hits-button"
      data-expand-hits
      data-expanded="false"
    >
      Show {{ paper.hidden_hit_count }} more occurrences
    </button>
    {% endif %}
    {% endif %}
  </article>
  {% endfor %}
  {% else %}
  <div class="no-results panel">No results found for your query.</div>
  {% endif %}
{% endif %}
"""


SETTINGS_CONTENT_TEMPLATE = r"""
{% if error %}
<div class="message error">{{ error }}</div>
{% endif %}
{% if success %}
<div class="message success">{{ success }}</div>
{% endif %}

<section class="panel">
  <h2>General Settings</h2>
  <p class="panel-intro">
    These values are saved to your user config file and become the defaults for the web UI and CLI. Environment variables still override them at runtime.
  </p>

  <div class="settings-summary">
    <div class="mini-card">
      <span class="label">Config File</span>
      <span class="value">{{ config_path }}</span>
    </div>
    <div class="mini-card">
      <span class="label">Linked Files</span>
      <span class="value">{{ form.get('base_attachment_path') or 'Not configured' }}</span>
    </div>
  </div>

  <form action="/settings" method="POST">
    <div class="message success" style="margin-bottom: 1.5rem;">
      ZotGrep always uses Zotero's local API because PDF full-text search depends on the local Zotero client.
    </div>

    <div class="form-row-2">
      <div class="form-group">
        <label for="zotero_user_id">Zotero User ID</label>
        <input type="text" id="zotero_user_id" name="zotero_user_id"
               value="{{ form.get('zotero_user_id', '0') }}">
        <small>Leave as <code>0</code> unless you have a specific local-library setup that requires a different value.</small>
      </div>
      <div class="form-group">
        <label for="library_type">Library Type</label>
        <select id="library_type" name="library_type">
          <option value="user" {{ 'selected' if form.get('library_type') == 'user' else '' }}>user</option>
          <option value="group" {{ 'selected' if form.get('library_type') == 'group' else '' }}>group</option>
        </select>
      </div>
    </div>

    <div class="form-group">
      <label for="zotero_api_key">Zotero API Key</label>
      <input type="password" id="zotero_api_key" name="zotero_api_key"
             value="{{ form.get('zotero_api_key', 'local') }}">
      <small>For the local Zotero API this should normally remain <code>local</code>.</small>
    </div>

    <div class="form-group">
      <label for="base_attachment_path">Base Attachment Path</label>
      <input type="text" id="base_attachment_path" name="base_attachment_path"
             value="{{ form.get('base_attachment_path', '') }}"
             placeholder="Optional; only for linked files">
      <small>Can be left empty if you exclusively use Zotero-stored files. Needs to be set if your PDFs are linked attachments (managed, for instance, via ZotMoov).</small>
    </div>

    <div class="form-row-2">
      <div class="form-group">
        <label for="max_results_stage1">Default Max Results</label>
        <input type="number" id="max_results_stage1" name="max_results_stage1"
               value="{{ form.get('max_results_stage1', 100) }}" min="1">
      </div>
      <div class="form-group">
        <label for="context_sentence_window">Default Context Window</label>
        <input type="number" id="context_sentence_window" name="context_sentence_window"
               value="{{ form.get('context_sentence_window', 2) }}" min="0">
      </div>
    </div>

    <div class="btn-row">
      <button type="submit" class="btn btn-primary">Save Settings</button>
      <a href="/" class="btn btn-outline">Back To Search</a>
    </div>
  </form>

  <p class="note" style="margin-top: 1rem;">
    Runtime precedence is: package defaults, then this config file, then environment variables, then explicit per-run overrides.
  </p>
</section>
"""
