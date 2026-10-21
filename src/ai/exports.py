from src.reports.traceability import build_matrix_bytes

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def traceability_xlsx():
    """Returns (bytes, filename, mime) for st.download_button."""
    return build_matrix_bytes(), "traceability.xlsx", XLSX_MIME
