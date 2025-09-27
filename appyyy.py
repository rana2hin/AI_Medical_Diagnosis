import pandas as pd
from pathlib import Path
import os
import google.generativeai as genai

from shiny import App, reactive, render, ui, req
from shiny.types import ActionButtonValue
from faicons import icon_svg

# --------------------------------------------------------------------------
# Configure Gemini API
# --------------------------------------------------------------------------
try:
    # It's highly recommended to set this as an environment variable
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    # Initialize the model
    model = genai.GenerativeModel('gemini-2.5-pro')
except (ValueError, FileNotFoundError) as e:
    # If the API key is not set, the app can still run, but the diagnosis feature will be disabled.
    print(f"Warning: Gemini API not configured. {e}")
    model = None


# --------------------------------------------------------------------------
# Load Data from CSV
# --------------------------------------------------------------------------
try:
    file_path = Path(__file__).parent / "hypothetical_patient_data.csv"
    initial_df = pd.read_csv(file_path).fillna("").astype(str)
    # Ensure ID is an integer for proper row matching
    initial_df['ID'] = pd.to_numeric(initial_df['ID'], errors='coerce').astype('Int64')

except FileNotFoundError:
    print("Warning: 'hypothetical_patient_data.csv' not found. Starting with an empty table.")
    initial_df = pd.DataFrame(columns=[
        "ID", "Age", "Gender", "Height (cm)", "Weight (kg)", "BMI",
        "BP", "Symptoms", "Medication History"
    ])

# --------------------------------------------------------------------------
# Shiny App UI (Corrected)
# --------------------------------------------------------------------------
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.navset_pill_list(
            ui.nav_panel("Patients", value="patients"),
            ui.nav_panel("Diagnose", value="diagnose"),
            id="main_navset",
        ),
        title="Menu",
    ),

    ui.output_ui("page_content"),

    ui.tags.style("""
        .patient-card { border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); background-color: #fff; }
        .patient-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .patient-title { font-size: 1.2em; font-weight: bold; }
        .patient-body { font-size: 0.9em; }
        .btn-group-sm > .btn { padding: .5rem .5rem; font-size: .875rem; line-height: 1.5; border-radius: .2rem; }
    """),
    title="AI Patient Diagnosis"
)


# --------------------------------------------------------------------------
# Shiny App Server Logic (with Page Switching)
# --------------------------------------------------------------------------
def server(input, output, session):

    # === Reactive Values ===
    patient_df = reactive.Value(initial_df)
    active_patient_id = reactive.Value(None)
    diagnosis_result = reactive.Value("") # Store AI diagnosis result

    # === Main Page Content Router ===
    @output
    @render.ui
    def page_content():
        """
        Acts as a router to display UI based on the selected nav item.
        """
        if input.main_navset() == "patients":
            return ui.div(
                ui.div(
                    ui.input_action_button("add_new", "+ New", class_="btn-primary"),
                    style="display: flex; justify-content: flex-end; padding-bottom: 1rem;"
                ),
                ui.output_ui("patient_list"),
            )

        if input.main_navset() == "diagnose":
            # If "Diagnose" is selected, return its UI
            return ui.div(
                ui.h2("AI-Powered Diagnosis"),
                ui.card(
                    ui.output_ui("diagnose_patient_selector"),
                    ui.output_ui("diagnose_patient_details"),
                    ui.input_action_button("run_diagnosis", "Run Diagnosis", class_="btn-success"),
                ),
                ui.card(
                    ui.h4("Diagnosis Result:"),
                    ui.output_ui("diagnosis_result_ui"),
                ),
            )

    # === Data Display Logic (for Patients page) ===
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

    # === Modal Generation Function ===
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

    # === Diagnose Page Logic (MODIFIED) ===

    @output
    @render.ui
    def diagnose_patient_selector():
        """Creates a dropdown select input for patients."""
        df = patient_df.get()
        if df.empty:
            return ui.p("No patients available to diagnose. Please add a patient first.", style="color: red;")
        choices = {str(pid): f"Patient ID: {pid}" for pid in df["ID"]}
        return ui.input_select(
            "selected_patient_id", "1. Select a Patient", choices=choices
        )

    @output
    @render.ui
    def diagnose_patient_details():
        """Displays the details of the patient selected in the dropdown."""
        req(input.selected_patient_id())
        df = patient_df.get()
        patient_id = int(input.selected_patient_id())
        patient_series = df[df["ID"] == patient_id].iloc[0]

        return ui.div(
            ui.tags.b("Selected Patient Details:"),
            ui.p(
                f"Age: {patient_series['Age']}, ",
                f"Gender: {patient_series['Gender']}, ",
                f"BP: {patient_series['BP']}"
            ),
            ui.tags.b("Symptoms:"),
            ui.p(f"{patient_series['Symptoms']}"),
        )

    @reactive.Effect
    @reactive.event(input.run_diagnosis)
    def _():
        """
        Runs the diagnosis by sending patient data to the Gemini API.
        """
        req(input.selected_patient_id())
        
        # Check if the model was initialized successfully
        if not model:
            error_message = "ERROR: Gemini API is not configured. Please set the GOOGLE_API_KEY environment variable."
            diagnosis_result.set(error_message)
            ui.notification_show(error_message, duration=10, type="error")
            return

        df = patient_df.get()
        patient_id = int(input.selected_patient_id())
        patient = df[df["ID"] == patient_id].iloc[0]

        # Show a notification that analysis has started
        ui.notification_show("Running AI diagnosis...", duration=5, type="default")
        
        # --- NEW: Gemini API Integration ---
        # Create a detailed prompt for the AI model
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
            # Generate content using the API
            response = model.generate_content(prompt)
            # Update the reactive value with the AI's response text
            diagnosis_result.set(response.text)
            ui.notification_show("Diagnosis complete!", duration=3, type="success")
        except Exception as e:
            # Handle potential API errors gracefully
            error_message = f"An error occurred with the Gemini API: {e}"
            print(error_message)
            diagnosis_result.set(error_message)
            ui.notification_show("Failed to get diagnosis from API.", duration=5, type="error")


    @output
    @render.ui
    def diagnosis_result_ui():
        """Renders the diagnosis result from the reactive value."""
        result_text = diagnosis_result.get()
        if not result_text:
            return ui.p("Click 'Run Diagnosis' to see the result.", style="color: grey;")
        
        # Simple parsing to structure the output nicely
        # This assumes the AI follows the formatting instructions
        parts = result_text.split('\n')
        
        # Create UI elements for each part of the response
        output_elements = []
        for part in parts:
            if "suggested diagnosis:" in part.lower():
                output_elements.append(ui.tags.b(part))
            elif "suggested medication:" in part.lower():
                output_elements.append(ui.tags.b(part))
            elif part.strip(): # Add other lines as paragraphs
                output_elements.append(ui.p(part))
                
        return ui.div(*output_elements)

    # === CRUD Logic (No Changes Below This Line) ===

    # 1. CREATE: Show modal for a new patient
    @reactive.Effect
    @reactive.event(input.add_new)
    def _():
        ui.modal_show(patient_modal("Add New Patient"))

    # 2. SUBMIT NEW/COPY: Add the new data to the dataframe
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

    # 3. SUBMIT EDIT: Update an existing row
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

    # 4. CONFIRM DELETE: Perform the deletion
    @reactive.Effect
    @reactive.event(input.confirm_delete)
    def _():
        df = patient_df.get()
        delete_id = active_patient_id.get()
        updated_df = df[df["ID"] != delete_id].copy()
        patient_df.set(updated_df)
        ui.modal_remove()
        ui.notification_show(f"Patient ID: {delete_id} deleted.", duration=3, type="warning")

    # 5. MASTER OBSERVER: Detects which action button was clicked
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