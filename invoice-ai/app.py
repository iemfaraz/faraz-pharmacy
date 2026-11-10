"""Invoice AI — Streamlit entry point.

Milestone 7: full pipeline with review.
    upload -> preview -> [Run OCR] -> extracted fields + line items
           -> Review & Edit form -> Save

Streamlit architecture note (the trap this file is built around):
Streamlit reruns this entire script on EVERY interaction. st.button is
True only during the click's rerun — so extraction results must live in
st.session_state, keyed to the current file, or the review form would
vanish the moment the user edits a field.
"""

import pandas as pd
import streamlit as st

import config
from app.utils import files


@st.cache_resource(show_spinner="Loading OCR engine (first time takes ~30s)...")
def load_ocr_engine():
    from app.ocr.engine import get_engine
    return get_engine()


def run_pipeline(saved_path, page: int, use_preprocess: bool) -> dict:
    """OCR + extraction; returns everything the UI needs, ready to cache."""
    from app.extraction.rules import extract_fields
    from app.extraction.tables import extract_table
    from app.utils.logger import get_logger

    log = get_logger("pipeline")
    log.info("processing %s (page %d, preprocess=%s)",
             saved_path.name, page, use_preprocess)

    engine = load_ocr_engine()
    image = files.load_preview(saved_path, page)
    if use_preprocess:
        from app.preprocessing.pipeline import preprocess
        image = preprocess(image)
    lines = engine.extract(image)
    log.info("OCR: %d lines", len(lines))

    fields = extract_fields(lines)
    if config.USE_LLM_EXTRACTION:
        from app.extraction.llm import extract_with_llm, llm_available
        if llm_available():
            fields = extract_with_llm(lines, fields)
    table = extract_table(lines)
    log.info("extracted: vendor=%r total=%r items=%d",
             fields.vendor, fields.total, len(table.items))
    return {"lines": lines, "fields": fields, "table": table}


def render_results(result: dict, source_file: str) -> None:
    from app.review.screen import conf_icon, render_review

    lines, fields, table = result["lines"], result["fields"], result["table"]

    if not lines:
        st.warning("No text detected. Try the preprocessing toggle.")
        return

    with st.expander(f"Raw OCR — {len(lines)} lines", expanded=False):
        avg = sum(l.confidence for l in lines) / len(lines)
        st.caption(f"Average confidence: {avg:.1%}")
        st.dataframe(
            pd.DataFrame([{"Text": l.text, "Confidence": f"{l.confidence:.1%}"}
                          for l in lines]),
            use_container_width=True, height=300)

    with st.expander("Extraction summary", expanded=False):
        cols = st.columns(6)
        display = [("Vendor", fields.vendor), ("Date", fields.date),
                   ("Subtotal", fields.subtotal), ("Tax", fields.tax),
                   ("Total", fields.total), ("Currency", fields.currency)]
        for col, (label, value) in zip(cols, display):
            conf = fields.confidence.get(label.lower(), 0.0)
            col.metric(f"{conf_icon(conf)} {label}",
                       "—" if value is None else str(value),
                       delta=f"{conf:.0%} conf", delta_color="off")

    render_review(fields, table, source_file)


def render_dashboard() -> None:
    from datetime import date
    from app.database import repository as repo

    st.title("📊 Dashboard")
    if repo.count_invoices() == 0:
        st.info("No data yet — save a few invoices and this page comes alive.")
        return

    # date filter applies to every widget below
    c1, c2, c3 = st.columns([1, 1, 2])
    use_dates = c1.checkbox("Filter by date range", key="db_use_dates")
    date_from = c2.date_input("From", value=date(2015, 1, 1), key="db_from") if use_dates else None
    date_to = c3.date_input("To", value=date.today(), key="db_to") if use_dates else None

    stats = repo.stats_by_currency(date_from, date_to)
    if not stats:
        st.warning("No invoices in this date range.")
        return

    st.subheader("Totals by currency")
    st.caption("Amounts are never summed across currencies — a BDT and a USD "
               "invoice don't add.")
    known = [s for s in stats if s["currency"] != "?"]
    unknown = next((s for s in stats if s["currency"] == "?"), None)
    if known:
        cols = st.columns(max(len(known), 1))
        for col, s in zip(cols, known):
            col.metric(f"{s['currency']}",
                       f"{s['total_spend']:,.2f}",
                       f"{s['count']} invoice(s) · avg {s['avg_invoice']:,.2f}",
                       delta_color="off")
    if unknown:
        st.warning(f"{unknown['count']} invoice(s) have no currency set — their "
                   "amounts can't be summed with anything (not even each other). "
                   "Set the Currency field when reviewing, or re-save them.")

    months = [m for m in repo.monthly_totals(date_from, date_to)
              if m["currency"] != "?"]
    if months:
        st.subheader("Monthly spend")
        df = pd.DataFrame(months)
        pivot = df.pivot_table(index="month", columns="currency",
                               values="total", aggfunc="sum").fillna(0)
        st.bar_chart(pivot)
        st.caption("Series are separate currencies — compare shapes, not stacked heights. "
                   "Invoices without a currency are excluded from the chart.")

    st.subheader("Top vendors")
    tv = repo.top_vendors(5, date_from, date_to)
    st.dataframe(
        pd.DataFrame([{"Vendor": v["vendor"], "Spend": f"{v['total']:,.2f}",
                       "Currency": v["currency"], "Invoices": v["count"]}
                      for v in tv]),
        use_container_width=True, hide_index=True)

    st.subheader("Recent invoices")
    recent = repo.search_invoices(date_from=date_from, date_to=date_to, limit=10)
    st.dataframe(
        pd.DataFrame([{"ID": r["id"], "Vendor": r["vendor"], "Date": r["date"],
                       "Total": r["total"], "Currency": r["currency"],
                       "Items": len(r["items"])} for r in recent]),
        use_container_width=True, hide_index=True)
    st.caption("Open any invoice on the Saved Invoices page.")


def render_saved_invoices() -> None:
    from app.database import repository as repo
    from datetime import date

    st.title("📚 Saved invoices")
    n = repo.count_invoices()
    if n == 0:
        st.info("No invoices saved yet — process one on the Process Invoice page.")
        return
    st.caption(f"{n} invoice(s) stored")

    with st.expander("🔎 Search & filters", expanded=False):
        c1, c2 = st.columns(2)
        text = c1.text_input("Free text (vendor, filename, item)", key="sv_text")
        vendor = c2.text_input("Vendor", key="sv_vendor")
        c3, c4, c5, c6 = st.columns(4)
        use_dates = c3.checkbox("Filter by date", key="sv_use_dates")
        date_from = c4.date_input("From", value=date(2015, 1, 1), key="sv_from") if use_dates else None
        date_to = c5.date_input("To", value=date.today(), key="sv_to") if use_dates else None
        min_total = c6.number_input("Min total", min_value=0.0, value=0.0, key="sv_min")

    results = repo.search_invoices(
        text=text or None, vendor=vendor or None,
        date_from=date_from, date_to=date_to,
        min_total=min_total if min_total > 0 else None)
    if not results:
        st.warning("No invoices match these filters.")
        return

    st.dataframe(
        pd.DataFrame([{"ID": r["id"], "Vendor": r["vendor"], "Date": r["date"],
                       "Total": r["total"], "Currency": r["currency"],
                       "Items": len(r["items"]), "Saved": r["created_at"]}
                      for r in results]),
        use_container_width=True, hide_index=True)

    st.markdown("**Export current results** (respects the filters above):")
    from app.export import exporters as ex
    e1, e2, e3, e4 = st.columns(4)
    e1.download_button(
        "⬇️ Excel (.xlsx)", data=ex.to_excel(results),
        file_name=ex.export_filename("xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True)
    e2.download_button(
        "⬇️ CSV — invoices", data=ex.to_csv_invoices(results),
        file_name=ex.export_filename("csv"), mime="text/csv",
        use_container_width=True)
    e3.download_button(
        "⬇️ CSV — line items", data=ex.to_csv_items(results),
        file_name="items_" + ex.export_filename("csv"), mime="text/csv",
        use_container_width=True)
    e4.download_button(
        "⬇️ JSON", data=ex.to_json(results),
        file_name=ex.export_filename("json"), mime="application/json",
        use_container_width=True)

    ids = [r["id"] for r in results]
    sel = st.selectbox("Open invoice", ids,
                       format_func=lambda i: f"#{i} — " + next(
                           (f"{r['vendor']} {r['total']}" for r in results if r["id"] == i), ""),
                       key="sv_sel")
    inv = repo.get_invoice(sel)
    if inv:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.write(f"**{inv['vendor']}** — {inv['date']} — "
                     f"{inv['total']} {inv['currency'] or ''}")
            if inv["items"]:
                st.dataframe(pd.DataFrame(inv["items"]),
                             use_container_width=True, hide_index=True)
        with c2:
            st.caption(f"Source: {inv['source_file'] or '—'}")
            if st.checkbox("Confirm delete", key=f"sv_del_ok_{sel}"):
                if st.button("🗑️ Delete invoice", key=f"sv_del_{sel}"):
                    repo.delete_invoice(sel)
                    st.success(f"Invoice #{sel} deleted.")
                    st.rerun()


def render_demo_process() -> None:
    """Demo variant of the process page: pick a sample, see real extraction."""
    from app.demo import SAMPLES, demo_pipeline
    import config

    label = st.selectbox("Choose a sample receipt", list(SAMPLES.keys()))
    sample_file = SAMPLES[label]
    img_path = config.TEST_DATA_DIR / sample_file

    col_preview, col_main = st.columns([2, 3], gap="large")
    with col_preview:
        st.subheader("Invoice")
        if img_path.exists():
            st.image(str(img_path), use_column_width=True)
        else:
            st.caption("(sample image not bundled)")
        run = st.button("🔍 Run OCR & Extract", type="primary",
                        use_container_width=True)

    if run:
        st.session_state.pipeline_result = demo_pipeline(sample_file)
        st.session_state.pipeline_key = f"demo:{sample_file}"

    with col_main:
        result = st.session_state.get("pipeline_result")
        if result is None or not st.session_state.get("pipeline_key", "").startswith("demo:"):
            st.info("Pick a sample and click Run OCR to see extraction.")
        else:
            if result.get("demo_note"):
                st.caption("💡 " + result["demo_note"])
            render_results(result, sample_file)


def main() -> None:
    st.set_page_config(page_title="Invoice AI", page_icon="🧾", layout="wide")

    from app.database import repository as repo
    repo.init_db()

    page = st.sidebar.radio("Navigation",
                            ["Process Invoice", "Saved Invoices", "Dashboard"])
    if page == "Saved Invoices":
        render_saved_invoices()
        return
    if page == "Dashboard":
        render_dashboard()
        return

    st.title("🧾 Invoice AI")

    from app.demo import demo_mode_enabled
    demo = demo_mode_enabled()
    if demo:
        st.info("🎭 **Demo mode** — live OCR needs more memory than this free host "
                "provides, so OCR is precomputed for the sample receipts below. "
                "Everything else (review, edit, save, dashboard, export) is fully live. "
                "Run locally for live OCR on your own uploads — see the GitHub repo.")
        render_demo_process()
        return

    st.caption("Upload an invoice — review the extraction — save.")

    uploaded = st.file_uploader(
        "Choose an invoice file",
        type=[ext.lstrip(".") for ext in sorted(config.ALLOWED_EXTENSIONS)],
        accept_multiple_files=False,
        help=f"Max size: {config.MAX_FILE_SIZE_MB} MB",
    )
    if uploaded is None:
        st.info("👆 Choose a file to get started.")
        return

    file_bytes = uploaded.getvalue()
    check = files.validate_upload(uploaded.name, len(file_bytes))
    if not check.ok:
        st.error(check.error)
        return

    # save once per file; a NEW file also invalidates cached extraction
    file_key = f"{uploaded.name}:{len(file_bytes)}"
    if st.session_state.get("last_file_key") != file_key:
        st.session_state.last_file_key = file_key
        st.session_state.saved_path = files.save_upload(file_bytes, uploaded.name)
        st.session_state.pop("pipeline_result", None)
        st.session_state.pop("pipeline_key", None)
        # widget state from the previous invoice's review form must not leak
        for k in list(st.session_state.keys()):
            if k.startswith("rv_"):
                del st.session_state[k]
    saved_path = st.session_state.saved_path

    col_preview, col_main = st.columns([2, 3], gap="large")

    with col_preview:
        st.subheader("Invoice")
        use_preprocess = st.toggle("Apply preprocessing",
                                   value=config.PREPROCESS_DEFAULT_ON,
                                   help="OpenCV pipeline — off by default "
                                        "(benchmarked: PP-OCRv4 does this internally)")
        page = 0
        if files.is_pdf(saved_path):
            n_pages = files.pdf_page_count(saved_path)
            if n_pages > 1:
                page = st.number_input("Page", 1, n_pages, 1) - 1
        try:
            image = files.load_preview(saved_path, page)
        except Exception as exc:
            st.error(f"Could not render a preview: {exc}")
            return
        if use_preprocess:
            from app.preprocessing.pipeline import preprocess_to_pil
            tab_o, tab_p = st.tabs(["Original", "Preprocessed"])
            tab_o.image(image, use_column_width=True)
            with st.spinner("Preprocessing..."):
                tab_p.image(preprocess_to_pil(image), use_column_width=True)
        else:
            st.image(image, use_column_width=True)

        if st.button("🔍 Run OCR & Extract", type="primary", use_container_width=True):
            try:
                with st.spinner("Reading and extracting..."):
                    st.session_state.pipeline_result = run_pipeline(
                        saved_path, page, use_preprocess)
                    st.session_state.pipeline_key = f"{file_key}:{page}:{use_preprocess}"
            except Exception:
                from app.utils.logger import get_logger
                get_logger("pipeline").exception("pipeline failed for %s", saved_path.name)
                st.error("Something went wrong while processing this file. "
                         "The image may be corrupted or in an unsupported format — "
                         "details are in logs/invoice_ai.log.")

    with col_main:
        result = st.session_state.get("pipeline_result")
        if result is None:
            st.info("Run OCR to see extraction results here.")
        else:
            current = f"{file_key}:{page}:{use_preprocess}"
            if st.session_state.get("pipeline_key") != current:
                st.warning("Settings or page changed since the last run — "
                           "results below are from the previous run. Re-run OCR to refresh.")
            render_results(result, saved_path.name)


if __name__ == "__main__":
    main()