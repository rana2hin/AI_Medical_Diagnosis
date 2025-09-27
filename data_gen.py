import pandas as pd
import numpy as np
from faker import Faker
import random

# Initialize Faker
fake = Faker()

# --- Expanded and Categorized Lists ---

# Symptoms for acute/common illnesses (more likely in younger patients)
acute_symptoms = [
    "Fever", "Cough", "Sore Throat", "Headache", "Nausea", "Fatigue",
    "Runny Nose", "Body Aches", "Vomiting", "Diarrhea"
]

# Symptoms for chronic conditions (more likely in older patients)
chronic_symptoms = [
    "Shortness of Breath", "Chest Pain", "Dizziness", "Joint Pain",
    "Swelling in Legs", "Persistent Cough", "High Blood Sugar", "Blurred Vision"
]

# Medications for acute/common illnesses
acute_medications = [
    "Ibuprofen", "Acetaminophen", "Amoxicillin", "Cough Syrup",
    "Decongestant", "Antihistamine", "Oseltamivir"
]

# Medications for chronic conditions
chronic_medications = [
    "Lisinopril", "Metformin", "Simvastatin", "Amlodipine", "Metoprolol",
    "Warfarin", "Insulin", "Aspirin", "Furosemide"
]


# --- Data Generation Function ---

def create_realistic_patient_data(num_patients=20):
    patient_data = []
    for i in range(1, num_patients + 1):
        age = random.randint(18, 85)
        gender = random.choice(["Male", "Female"])

        # Generate height based on gender (in cm)
        if gender == "Male":
            height_cm = round(random.uniform(165, 195), 2)
        else:
            height_cm = round(random.uniform(150, 180), 2)

        # Generate weight based on height (in kg) with some noise
        # Base weight on a healthy BMI range (18.5-24.9) and add variation
        base_bmi = random.uniform(19, 30)
        weight_kg = round(base_bmi * ((height_cm / 100) ** 2) + random.uniform(-5, 5), 2)
        
        # Calculate final BMI
        bmi = round(weight_kg / ((height_cm / 100) ** 2), 2)

        # Generate BP based on age and BMI
        systolic_base = 110 + (age * 0.2) + (bmi * 0.3)
        diastolic_base = 70 + (age * 0.1) + (bmi * 0.2)
        systolic = int(systolic_base + random.randint(-10, 10))
        diastolic = int(diastolic_base + random.randint(-5, 8))
        bp = f"{systolic}/{diastolic}"
        
        # Assign symptoms and medications based on age
        if age < 45:
            # Younger patients more likely to have acute issues
            num_symptoms = random.randint(1, 2)
            symptoms = ", ".join(random.sample(acute_symptoms, k=num_symptoms))
            medications = ", ".join(random.sample(acute_medications, k=random.randint(0, 2)))
        else:
            # Older patients have a mix, but higher chance of chronic issues
            if random.random() > 0.4: # 60% chance of chronic issue focus
                symptoms = ", ".join(random.sample(chronic_symptoms, k=random.randint(1, 3)))
                medications = ", ".join(random.sample(chronic_medications, k=random.randint(1, 3)))
            else: # 40% chance of an acute issue
                symptoms = ", ".join(random.sample(acute_symptoms, k=random.randint(1, 2)))
                medications = ", ".join(random.sample(acute_medications, k=random.randint(0, 2)))
        
        # Ensure medication history is sometimes empty
        if not medications:
            medications = "None"


        patient = {
            "ID": i,
            "Age": age,
            "Gender": gender,
            "Height (cm)": height_cm,
            "Weight (kg)": weight_kg,
            "BMI": bmi,
            "BP": bp,
            "Symptoms": symptoms,
            "Medication History": medications
        }
        patient_data.append(patient)

    return pd.DataFrame(patient_data)


# --- Generate and Display the DataFrame ---

df_patients = create_realistic_patient_data(20)
print(df_patients)

# To save this data to a CSV file for your Shiny app:
df_patients.to_csv('hypothetical_patient_data.csv', index=False)
