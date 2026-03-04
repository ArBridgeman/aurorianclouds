"""Streamlit application for banking CSV cleaning."""

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from banking_helpers.excel_export import write_excel_with_validation
from banking_helpers.processor import CSVProcessor
from omegaconf import DictConfig, OmegaConf


def get_bank_configs(config_dir: Path) -> dict[str, str]:
    """
    Get available bank configurations.

    Args:
        config_dir: Path to config directory

    Returns:
        Dictionary mapping bank display names to config file names
    """
    banks_dir: Path = config_dir / "banks"
    banks: dict[str, str] = {}

    if banks_dir.exists():
        for config_file in banks_dir.glob("*.yaml"):
            bank_config: DictConfig = OmegaConf.load(config_file)
            bank_name: str = bank_config.get("bank_name", config_file.stem)
            banks[bank_name] = config_file.stem

    return banks


def main() -> None:
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Banking CSV Preparer", page_icon="💰", layout="wide"
    )

    st.title("💰 Banking CSV Preparer")
    st.markdown(
        "Upload your banking CSV and get a cleaned version "
        "ready for your spreadsheet."
    )

    # Load configuration
    config_dir: Path = Path(__file__).parent / "config"
    main_config: DictConfig = OmegaConf.load(config_dir / "config.yaml")
    output_config: DictConfig = OmegaConf.load(
        config_dir / "output_format.yaml"
    )

    # Get available banks
    banks: dict[str, str] = get_bank_configs(config_dir)

    if not banks:
        st.error(
            "No bank configurations found. "
            "Please add bank configs to config/banks/"
        )
        return

    # File upload
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

    # Bank selection
    bank_names: list[str] = list(banks.keys())
    selected_bank_name: str = st.selectbox("Select bank format", bank_names)
    selected_bank_key: str = banks[selected_bank_name]

    if uploaded_file is not None:
        # Load bank config
        bank_config: DictConfig = OmegaConf.load(
            config_dir / "banks" / f"{selected_bank_key}.yaml"
        )

        # Process button
        if st.button("Process CSV"):
            try:
                # Read file content (reset file pointer first)
                uploaded_file.seek(0)
                csv_content: bytes = uploaded_file.read()

                # Process
                processor: CSVProcessor = CSVProcessor(
                    bank_config=bank_config,
                    output_config=output_config,
                    date_format=main_config.date_format,
                )

                cleaned_df: pd.DataFrame = processor.process(csv_content)

                # Display preview
                st.success(
                    f"✅ Processed {len(cleaned_df)} transactions successfully!"
                )
                st.dataframe(cleaned_df.head(20), use_container_width=True)

                # Prepare CSV output
                csv_output: str = cleaned_df.to_csv(index=False)

                # Download/Copy Options Section
                st.markdown("### Download & Copy Options")

                # Get validation config for Excel export
                validation_path: Path = config_dir / "validation.yaml"
                validation_config: dict[str, list[Any]] = {}
                if validation_path.exists():
                    validation_config = (
                        OmegaConf.to_container(
                            OmegaConf.load(validation_path), resolve=True
                        )
                        or {}
                    )

                excel_buffer = io.BytesIO()
                write_excel_with_validation(
                    cleaned_df, excel_buffer, validation_config
                )
                excel_bytes: bytes = excel_buffer.getvalue()

                # Download buttons (3 columns)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv_output,
                        file_name=f"cleaned_{uploaded_file.name}",
                        mime="text/csv",
                        use_container_width=True,
                    )
                with col2:
                    st.download_button(
                        label="📊 Download Excel",
                        data=excel_bytes,
                        file_name=(
                            f"cleaned_{Path(uploaded_file.name).stem}.xlsx"
                        ),
                        mime=(
                            "application/vnd.openxmlformats-"
                            "officedocument.spreadsheetml.sheet"
                        ),
                        use_container_width=True,
                    )
                with col3:
                    # Copy to clipboard button using HTML/JavaScript
                    csv_json = json.dumps(csv_output)
                    copy_button_html = f"""
                    <div style="display: flex; gap: 10px;">
                        <button id="copy-btn" onclick="copyToClipboard()"
                            style="
                            background-color: #FF6B6B;
                            color: white;
                            padding: 10px 20px;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 14px;
                            width: 100%;
                            font-weight: bold;
                            transition: all 0.3s;
                        "
                            onmouseover="this.style.backgroundColor='#FF5252'"
                            onmouseout="this.style.backgroundColor='#FF6B6B'">
                        📋 Copy to Clipboard
                        </button>
                    </div>
                    <script>
                    const csvData = {csv_json};
                    function copyToClipboard() {{
                        try {{
                            // Try modern clipboard API first
                            navigator.clipboard.writeText(csvData).then(
                                function() {{
                                    const btn = document.getElementById(
                                        'copy-btn');
                                    const originalText = btn.innerHTML;
                                    btn.innerHTML = '✅ Copied!';
                                    btn.style.backgroundColor = '#51CF66';
                                    setTimeout(function() {{
                                        btn.innerHTML = originalText;
                                        btn.style.backgroundColor =
                                            '#FF6B6B';
                                    }}, 2000);
                            }}).catch(function(err) {{
                                // Fallback: create temporary textarea
                                fallbackCopy(csvData);
                            }});
                        }} catch(err) {{
                            fallbackCopy(csvData);
                        }}
                    }}

                    function fallbackCopy(text) {{
                        const textarea = (
                            document.createElement('textarea'));
                        textarea.value = text;
                        textarea.style.position = 'fixed';
                        textarea.style.opacity = '0';
                        document.body.appendChild(textarea);
                        textarea.select();
                        try {{
                            document.execCommand('copy');
                            const btn = document.getElementById('copy-btn');
                            const originalText = btn.innerHTML;
                            btn.innerHTML = '✅ Copied!';
                            btn.style.backgroundColor = '#51CF66';
                            setTimeout(function() {{
                                btn.innerHTML = originalText;
                                btn.style.backgroundColor = '#FF6B6B';
                            }}, 2000);
                        }} catch(err) {{
                            alert('Failed to copy. ' +
                                'Please use Download CSV instead.');
                        }}
                        document.body.removeChild(textarea);
                    }}
                    </script>
                    """
                    components.html(copy_button_html, height=50)

                # CSV text area for manual copy/view
                st.markdown("### Or View/Copy from Text Area")
                st.text_area(
                    "CSV Content (select all and copy with Ctrl+A / Cmd+A, then Ctrl+C / Cmd+C)",
                    value=csv_output,
                    height=250,
                    disabled=True,
                    key="csv_output_area",
                    help=(
                        "This is a read-only view of your cleaned CSV. "
                        "Recommended: Use the Copy to Clipboard or Download buttons instead."
                    ),
                )

            except Exception as e:
                st.error(f"❌ Error processing CSV: {str(e)}")
                st.exception(e)


if __name__ == "__main__":
    main()
