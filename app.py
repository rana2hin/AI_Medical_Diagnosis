import pandas as pd
from pathlib import Path
import os
import google.generativeai as genai
import re # Keep re for safety, but primary logic will be string splitting

# MODIFIED: Add imports for Plotly gauge
import plotly.graph_objects as go
from shinywidgets import render_plotly, output_widget

from shiny import App, reactive, render, ui, req
from shiny.types import ActionButtonValue
from faicons import icon_svg

# --------------------------------------------------------------------------
# Configure Gemini API
# --------------------------------------------------------------------------
try:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    # Using the standard, reliable model name
    model = genai.GenerativeModel('gemini-2.5-pro')
except (ValueError, FileNotFoundError) as e:
    print(f"Warning: Gemini API not configured. {e}")
    model = None

# --------------------------------------------------------------------------
# Load Data from CSV
# --------------------------------------------------------------------------
try:
    file_path = Path(__file__).parent / "hypothetical_patient_data.csv"
    initial_df = pd.read_csv(file_path).fillna("").astype(str)
    initial_df['ID'] = pd.to_numeric(initial_df['ID'], errors='coerce').astype('Int64')
except FileNotFoundError:
    print("Warning: 'hypothetical_patient_data.csv' not found. Starting with an empty table.")
    initial_df = pd.DataFrame(columns=[
        "ID", "Age", "Gender", "Height (cm)", "Weight (kg)", "BMI",
        "BP", "Symptoms", "Medication History"
    ])

# --------------------------------------------------------------------------
# Shiny App UI (MODIFIED FOR PLOTLY GAUGE)
# --------------------------------------------------------------------------
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.navset_pill_list(
            ui.nav_panel("Diagnosis", value="diagnose"),
            ui.nav_panel("Patients", value="patients"),
            id="main_navset",
        ),
        title="Menu",
    ),
    ui.output_ui("page_content"),
    ui.tags.style("""
        /* Existing Patient List Styles */
        .patient-card { border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); background-color: #fdfdfd; }
        .patient-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .patient-title { font-size: 1.2em; font-weight: bold; }
        .patient-body { font-size: 0.9em; }
        .btn-group-sm > .btn { padding: .5rem .5rem; font-size: .875rem; line-height: 1.5; border-radius: .2rem; }

        /* Diagnosis Page Styles */
        .diag-page-container { padding: 1rem; }
        .diag-main-layout { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; align-items: flex-start; }
        .patient-details-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
        .info-card { background-color: #fff; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; min-height: 140px; display: flex; flex-direction: column; justify-content: center; }
        
        /* CHANGE 1: Bigger and Bolder Card Titles */
        .info-card-title { font-size: 1.1em; font-weight: 700; color: #333; margin-bottom: 8px; text-transform: uppercase; }
        
        .info-card-value { font-size: 2.2em; font-weight: 700; color: #1a1a1a; }
        .info-card-value.gender-icon { font-size: 3.0em; }

        /* CHANGE 2: Taller and Narrower Gauge Chart Container */
        .bmi-card-container {
            padding: 5px !important;
            grid-column: 1 / -1;
            min-height: 300px; /* Increased height */
            max-width: 450px; /* Added max-width */
            margin-left: auto; /* Center the container */
            margin-right: auto;
        }

        /* CHANGE 3: Placed BP and Symptoms cards in one row by removing grid-column span */
        .symptoms-card {
            /* grid-column: 1 / -1; <-- This line was removed */
            min-height: 225px; /* Matched height to BP card for alignment */
            text-align: left;
            justify-content: flex-start; /* Align content to top */
        }
        .bp-card {
             min-height: 225px; /* Increased height to balance with symptoms card */
        }
        .symptoms-content { max-height: 150px; overflow-y: auto; }
        
        .bp-card .info-card-value { font-size: 1.2em; }
        .progress-bar-container { margin-top: 10px; }
        .progress-bar { height: 15px; background-color: #e9ecef; border-radius: .25rem; overflow: hidden; }
        .progress-bar-inner { height: 100%; background-color: #dc3545; transition: width 0.6s ease; }
        
        .ai-result-card { background-color: #fff; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .ai-result-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 1.2em; font-weight: 600; }
        .ai-result-body { color: #333; min-height: 100px; }
        .ai-caution { text-align: center; padding: 15px; margin-top: 20px; font-weight: 600; color: #856404; background-color: #fff3cd; border: 1px solid #ffeeba; border-radius: 8px; }
    """),
    title="AI Patient Diagnosis"
)

# --------------------------------------------------------------------------
# Shiny App Server Logic
# --------------------------------------------------------------------------
def server(input, output, session):

    # === Reactive Values ===
    patient_df = reactive.Value(initial_df)
    active_patient_id = reactive.Value(None)
    diagnosis_result = reactive.Value("")

    # === Main Page Content Router (MODIFIED for Gauge) ===
    @output
    @render.ui
    def page_content():
        if input.main_navset() == "patients":
            # ... (Patient list UI is unchanged)
            return ui.div(
                ui.div(
                    ui.input_action_button("add_new", "+ New", class_="btn-primary"),
                    style="display: flex; justify-content: flex-end; padding: 1rem;"
                ),
                ui.output_ui("patient_list"),
            )
        if input.main_navset() == "diagnose":
            return ui.div(
                {"class": "diag-page-container"},
                ui.h2("AI-Powered Diagnosis"),
                ui.output_ui("diagnose_patient_selector"),
                ui.hr(),
                ui.panel_conditional(
                    "input.selected_patient_id",
                    ui.div(
                        {"class": "diag-main-layout"},
                        # Left Column: Patient Details
                        ui.div(
                            ui.div(
                                {"class": "patient-details-grid"},
                                ui.output_ui("age_card"),
                                ui.output_ui("gender_card"),
                                # MODIFIED: Use a container for the BMI card that will hold the widget
                                ui.div(
                                    {"class": "info-card bmi-card-container"},
                                    output_widget("bmi_gauge_widget") # Use output_widget for plotly
                                ),
                                ui.output_ui("bp_card"),
                                ui.output_ui("symptoms_card"),
                            )
                        ),
                        # Right Column: AI Results
                        ui.div(
                            ui.input_action_button("run_diagnosis", "Run Diagnosis", class_="btn-success btn-lg w-70"),
                            ui.output_ui("suggested_diagnosis_card"),
                            ui.output_ui("suggested_medication_card"),
                        )
                    ),
                    ui.div(
                        {"class": "ai-caution"},
                        ui.p("Please select a patient to view their details.")
                    ),
                    ui.output_ui("caution_footer")
                )
            )

    # === Diagnosis Page Logic ===

    @output
    @render.ui
    def diagnose_patient_selector():
        df = patient_df.get()
        choices = {str(pid): f"Patient ID: {pid}" for pid in df["ID"]}
        return ui.input_select(
            "selected_patient_id", "Select Patient", choices=["", *choices], selected=""
        )

    @reactive.Calc
    def selected_patient_data():
        req(input.selected_patient_id())
        df = patient_df.get()
        patient_id = int(input.selected_patient_id())
        return df[df["ID"] == patient_id].iloc[0]

    # --- UI Rendering for each card ---
    @output
    @render.ui
    def age_card():
        patient = selected_patient_data()
        return ui.div(
            {"class": "info-card"},
            ui.div("Age", class_="info-card-title"),
            ui.div(patient.get('Age', 'N/A'), class_="info-card-value")
        )

    # MODIFIED: Fixed gender icon names
    @output
    @render.ui
    def gender_card():
        patient = selected_patient_data()
        gender = patient.get('Gender', 'Other').lower()
        # Use correct Font Awesome icon names: 'mars', 'venus'
        icon = "mars" if gender == "male" else "venus" if gender == "female" else "neuter"
        return ui.div(
            {"class": "info-card"},
            ui.div("Gender", class_="info-card-title"),
            ui.div(icon_svg(icon), class_="info-card-value gender-icon")
        )
    
    # NEW: Plotly gauge for BMI
    @output
    @render_plotly
    def bmi_gauge_widget():
        patient = selected_patient_data()
        try:
            bmi_value = float(patient.get('BMI', 0))
        except (ValueError, TypeError):
            bmi_value = 0

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=bmi_value,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Body Mass Index (BMI)", 'font': {'size': 20}},
            gauge={
                'axis': {'range': [10, 40], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': "#28a745" if 18.5 <= bmi_value <= 24.9 else "#ffc107" if 25 <= bmi_value <= 29.9 else "#dc3545"},
                'bgcolor': "white",
                'borderwidth': 1,
                'bordercolor': "gray",
                'steps': [
                    {'range': [10, 18.5], 'color': 'lightblue'},      # Underweight
                    {'range': [18.5, 24.9], 'color': 'lightgreen'},   # Normal
                    {'range': [25, 29.9], 'color': 'lightyellow'},    # Overweight
                    {'range': [30, 40], 'color': 'lightcoral'}        # Obese
                ],
            }))
        
        # Make it fit nicely in the card
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', # Transparent background
            margin=dict(l=20, r=20, t=40, b=20) # Adjust margins
        )
        return fig

    @output
    @render.ui
    def bp_card():
        patient = selected_patient_data()
        bp = patient.get('BP', '0/0')
        # Ensure data is clean before splitting
        if isinstance(bp, str) and '/' in bp:
            sys_str, dia_str = bp.split('/')
            sys = int(sys_str) if sys_str.isdigit() else 0
            dia = int(dia_str) if dia_str.isdigit() else 0
        else:
            sys, dia = 0, 0
        
        # Normalize for progress bar (max 200 for sys, 120 for dia)
        sys_perc = min((sys / 200) * 100, 100) if sys > 0 else 0
        dia_perc = min((dia / 120) * 100, 100) if dia > 0 else 0
        
        return ui.div(
            {"class": "info-card bp-card"},
            ui.div("Blood Pressure", class_="info-card-title"),
            ui.div(f"{sys} / {dia}", class_="info-card-value"),
            ui.div(
                {"class": "progress-bar-container"},
                ui.p("Systolic", style="margin: 5px 0 2px; font-size: 0.8em;"),
                ui.div({"class": "progress-bar"}, ui.div({"class": "progress-bar-inner", "style": f"width: {sys_perc}%;"})),
                ui.p("Diastolic", style="margin: 5px 0 2px; font-size: 0.8em;"),
                ui.div({"class": "progress-bar"}, ui.div({"class": "progress-bar-inner", "style": f"width: {dia_perc}%; background-color: #198754;"})),
            )
        )

    @output
    @render.ui
    def symptoms_card():
        patient = selected_patient_data()
        return ui.div(
            {"class": "info-card symptoms-card"},
            ui.div("Symptoms", class_="info-card-title"),
            ui.div(patient.get('Symptoms', 'N/A'), class_="symptoms-content")
        )

    # MODIFIED: Reverted prompt to be simpler and more reliable
    @reactive.Effect
    @reactive.event(input.run_diagnosis)
    def _():
        req(input.selected_patient_id())
        if not model:
            msg = "ERROR: Gemini API is not configured."
            diagnosis_result.set(msg)
            ui.notification_show(msg, duration=10, type="error")
            return

        patient = selected_patient_data()
        ui.notification_show("Running AI diagnosis...", duration=5)

        # REVERTED PROMPT: Simpler prompt is more reliable
        prompt = f"""
        Analyze the following patient data and provide a concise 'Suggested Diagnosis' and 'Suggested Medication'.
        Format the response with 'Suggested Diagnosis:' on one line and 'Suggested Medication:' on the next.
        This is for a hypothetical tool and not real medical advice.

        PATIENT DATA:
        - Age: {patient.get('Age', 'N/A')}
        - Gender: {patient.get('Gender', 'N/A')}
        - Blood Pressure: {patient.get('BP', 'N/A')}
        - Current Symptoms: {patient.get('Symptoms', 'N/A')}
        - Medication History: {patient.get('Medication History', 'N/A')}
        - Height (cm): {patient.get('Height (cm)', 'N/A')}
        - Weight (kg): {patient.get('Weight (kg)', 'N/A')}
        - BMI: {patient.get('BMI', 'N/A')}

        RESPONSE:
        """
        try:
            response = model.generate_content(prompt)
            diagnosis_result.set(response.text)
            ui.notification_show("Diagnosis complete!", duration=3, type="success")
        except Exception as e:
            msg = f"An error occurred with the Gemini API: {e}"
            diagnosis_result.set(msg)
            ui.notification_show("Failed to get diagnosis from API.", duration=5, type="error")

    # MODIFIED: Use text processing to parse the AI response
    @output
    @render.ui
    def suggested_diagnosis_card():
        result_text = diagnosis_result.get()
        content = "Click 'Run Diagnosis' to see results."
        
        if result_text and "Suggested Diagnosis:" in result_text:
            # Split the text at "Suggested Diagnosis:" and take the second part
            after_diag_keyword = result_text.split("Suggested Diagnosis:")[1]
            # Then, split that part at "Suggested Medication:" to isolate the diagnosis
            if "Suggested Medication:" in after_diag_keyword:
                content = after_diag_keyword.split("Suggested Medication:")[0].strip()
            else:
                content = after_diag_keyword.strip()

        return ui.div(
            {"class": "ai-result-card"},
            ui.div({"class": "ai-result-header"}, icon_svg("stethoscope"), "Suggested Diagnosis"),
            ui.div(content, class_="ai-result-body")
        )

    # MODIFIED: Use text processing to parse the AI response
    @output
    @render.ui
    def suggested_medication_card():
        result_text = diagnosis_result.get()
        content = "" # Default to empty
        
        if result_text and "Suggested Medication:" in result_text:
            # Split the text and take everything after the keyword
            content = result_text.split("Suggested Medication:")[1].strip()

        return ui.div(
            {"class": "ai-result-card"},
            ui.div({"class": "ai-result-header"}, icon_svg("pills"), "Suggested Medication"),
            ui.div(content, class_="ai-result-body")
        )
        
    @output
    @render.ui
    def caution_footer():
        req(input.selected_patient_id())
        return ui.div("⚠️ Caution: AI might be wrong!", class_="ai-caution")

    # --- CRUD Logic (No Changes Below This Line) ---
    @output
    @render.ui
    def patient_list():
        df = patient_df.get()
        cards = []
        for index, row in df.iterrows():
            row_dict = row.to_dict()
            card = ui.div(
                ui.div(
                    ui.span(f"Patient ID: {row_dict.get('ID', 'N/A')}", class_="patient-title"),
                    ui.div(
                        ui.input_action_button(f"edit_{row_dict.get('ID', '')}", "", icon=icon_svg("pen-to-square"), class_="btn-sm btn-light"),
                        ui.input_action_button(f"copy_{row_dict.get('ID', '')}", "", icon=icon_svg("copy"), class_="btn-sm btn-light"),
                        ui.input_action_button(f"delete_{row_dict.get('ID', '')}", "", icon=icon_svg("trash"), class_="btn-sm btn-danger"),
                        class_="btn-group-sm",
                    ),
                    class_="patient-header",
                ),
                ui.div(
                    f"Age: {row_dict.get('Age', '')} | Gender: {row_dict.get('Gender', '')} | BP: {row_dict.get('BP', '')}", ui.br(),
                    f"Symptoms: {row_dict.get('Symptoms', '')}", ui.br(),
                    f"Medications: {row_dict.get('Medication History', '')}",
                    class_="patient-body",
                ),
                class_="patient-card", id=f"card_{row_dict.get('ID', '')}",
            )
            cards.append(card)
        return ui.div(*cards) if cards else ui.p("No patient records found.")

    def patient_modal(title, patient_data=None, action="new"):
        is_edit = action == "edit"
        data = patient_data if patient_data is not None else {}
        m = ui.modal(
            ui.input_numeric("modal_age", "Age", value=int(data.get("Age", 30))),
            ui.input_select("modal_gender", "Gender", choices=["Male", "Female", "Other"], selected=data.get("Gender", "Male")),
            ui.input_numeric("modal_height", "Height (cm)", value=float(data.get("Height (cm)", 170))),
            ui.input_numeric("modal_weight", "Weight (kg)", value=float(data.get("Weight (kg)", 70))),
            ui.input_text("modal_bp", "Blood Pressure", value=data.get("BP", "")),
            ui.input_text("modal_symptoms", "Symptoms", value=data.get("Symptoms", "")),
            ui.input_text("modal_meds", "Medication History", value=data.get("Medication History", "")),
            title=title,
            footer=ui.div(
                ui.modal_button("Cancel"),
                ui.input_action_button("submit_edit" if is_edit else "submit_new", "Save", class_="btn-primary"),
            ),
        )
        return m

    @reactive.Effect
    @reactive.event(input.add_new)
    def _():
        ui.modal_show(patient_modal("Add New Patient"))

    @reactive.Effect
    @reactive.event(input.submit_new)
    def _():
        df = patient_df.get()
        new_id = (df["ID"].max() + 1) if not df.empty else 1
        new_record = {
            "ID": new_id, "Age": input.modal_age(), "Gender": input.modal_gender(),
            "Height (cm)": input.modal_height(), "Weight (kg)": input.modal_weight(),
            "BMI": round(input.modal_weight() / ((input.modal_height() / 100) ** 2), 2),
            "BP": input.modal_bp(), "Symptoms": input.modal_symptoms(),
            "Medication History": input.modal_meds() or "None",
        }
        new_df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        patient_df.set(new_df)
        ui.modal_remove()
        ui.notification_show("Patient record added!", duration=3, type="success")

    @reactive.Effect
    @reactive.event(input.submit_edit)
    def _():
        df = patient_df.get().copy()
        edit_id = active_patient_id.get()
        row_index = df.index[df['ID'] == edit_id]
        if not row_index.empty:
            idx = row_index[0]
            df.loc[idx, "Age"] = str(input.modal_age())
            df.loc[idx, "Gender"] = input.modal_gender()
            df.loc[idx, "Height (cm)"] = str(input.modal_height())
            df.loc[idx, "Weight (kg)"] = str(input.modal_weight())
            df.loc[idx, "BMI"] = str(round(input.modal_weight() / ((input.modal_height() / 100) ** 2), 2))
            df.loc[idx, "BP"] = input.modal_bp()
            df.loc[idx, "Symptoms"] = input.modal_symptoms()
            df.loc[idx, "Medication History"] = input.modal_meds() or "None"
        patient_df.set(df)
        ui.modal_remove()
        ui.notification_show(f"Patient ID: {edit_id} updated.", duration=3, type="success")

    @reactive.Effect
    @reactive.event(input.confirm_delete)
    def _():
        df = patient_df.get()
        delete_id = active_patient_id.get()
        updated_df = df[df["ID"] != delete_id].copy()
        patient_df.set(updated_df)
        ui.modal_remove()
        ui.notification_show(f"Patient ID: {delete_id} deleted.", duration=3, type="warning")

    @reactive.Effect
    def _():
        if input.main_navset() == "patients":
            df = patient_df.get()
            valid_ids = df["ID"].dropna().astype(int)
            for patient_id in valid_ids:
                if input[f"edit_{patient_id}"]():
                    active_patient_id.set(patient_id)
                    patient_data = df[df["ID"] == patient_id].iloc[0].to_dict()
                    ui.modal_show(patient_modal(f"Edit Patient ID: {patient_id}", patient_data, action="edit"))
                    return
                if input[f"copy_{patient_id}"]():
                    patient_data = df[df["ID"] == patient_id].iloc[0].to_dict()
                    ui.modal_show(patient_modal(f"Copy from Patient ID: {patient_id}", patient_data, action="copy"))
                    return
                if input[f"delete_{patient_id}"]():
                    active_patient_id.set(patient_id)
                    ui.modal_show(
                        ui.modal(
                            f"Are you sure you want to delete patient ID: {patient_id}?",
                            title="Confirm Deletion",
                            footer=ui.div(
                                ui.modal_button("Cancel"),
                                ui.input_action_button("confirm_delete", "Delete", class_="btn-danger"),
                            ),
                        )
                    )
                    return

# --------------------------------------------------------------------------
# Create and run the app
# --------------------------------------------------------------------------
app = App(app_ui, server)