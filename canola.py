import csv
import sqlite3
import os

DATABASE = "canola.db"

def setup_tables(reset=False):
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()


    if reset:
        cursor.execute("DROP TABLE IF EXISTS assessment_data")
        cursor.execute("DROP TABLE IF EXISTS measurements")
        cursor.execute("DROP TABLE IF EXISTS PLOTS")
        cursor.execute("DROP TABLE IF EXISTS assessment_traits")
        cursor.execute("DROP TABLE IF EXISTS treatments")
        cursor.execute("DROP TABLE IF EXISTS trial_sites")
        cursor.execute("DROP TABLE IF EXISTS trials")

#1.Trials table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            trial_id INTEGER PRIMARY KEY,
            trial_code VARCHAR,
            trial_name VARCHAR,
            objective TEXT,
            target_crop VARCHAR,
            trial_start_date DATE,
            trial_end_date DATE,
            status VARCHAR,
            created_at DATETIME
        )
    """)
    #2.Trial Sites table

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trial_sites (
            site_id INTEGER PRIMARY KEY,
            trial_id INTEGER,
            site_name VARCHAR,
            latitude DECIMAL,
            longitude DECIMAL,
            soil_type VARCHAR,
            previous_crop VARCHAR,
            experimental_design VARCHAR,
            number_of_replicates INT,
            FOREIGN KEY (trial_id) REFERENCES trials(trial_id)
        )
    """)
    #3.Treatments table

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treatments (
            treatment_id INTEGER PRIMARY KEY,
            trial_id INTEGER,
            treatment_number INT,
            treatment_name VARCHAR,
            formulation_details TEXT,
            application_rate DECIMAL,
            rate_unit VARCHAR,
            FOREIGN KEY (trial_id) REFERENCES trials(trial_id)
        )
    """)
    #4.Plots table

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS PLOTS (
            plot_id INTEGER PRIMARY KEY,
            site_id INTEGER,
            plot_number INTEGER,
            replicate_number INTEGER,
            treatment_id INTEGER,
            row_index INTEGER,
            column_index INTEGER,
            FOREIGN KEY (site_id) REFERENCES trial_sites(site_id),
            FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id)
        )
    """)
    #5.Assessment Traits table

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessment_traits (
            trait_id INTEGER PRIMARY KEY,
            trial_id INTEGER,
            trait_name VARCHAR,
            methodology TEXT,
            unit_of_measurement VARCHAR,
            data_type VARCHAR,
            FOREIGN KEY (trial_id) REFERENCES trials(trial_id)
        )
    """)
    #6.Assessment Data table

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessment_data (
            data_id INTEGER PRIMARY KEY,
            trait_id INTEGER,
            plot_id INTEGER,
            numeric_value DECIMAL,
            assessment_date DATE,
            text_value TEXT,
            collected_by VARCHAR,
            notes TEXT,
            FOREIGN KEY (trait_id) REFERENCES assessment_traits(trait_id),
            FOREIGN KEY (plot_id) REFERENCES plots(plot_id)
        )
    """)

    #7.Measurements table

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            measurement_id INTEGER PRIMARY KEY,
            plot_id INTEGER,
            measurement_type VARCHAR,
            value DECIMAL,
            measurement_date DATE,
            FOREIGN KEY (plot_id) REFERENCES plots(plot_id)
        )
    """)

    conn.commit()
    conn.close()


def insert_trial_data():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    #Prevent duplicate sample data when the program runs again
    cursor.execute(
        "SELECT trial_id FROM trials WHERE trial_code = ?", ("CAN2026",)
    )

    existing_trial = cursor.fetchone()

    if existing_trial:
        print("Sample data already exists. Skipping insertion.")
        conn.close()
        return
    
    #1. Insert Trial
    cursor.execute("""
        INSERT INTO trials (trial_code, trial_name, objective, target_crop, trial_start_date, trial_end_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("CAN2026", "Canola Growth Trial 2026", "Evaluate growth and yield of canola under different treatments", "Canola", "2026-09-01", "2026-12-15", "Ongoing", "2026-09-01 10:00:00"))

    trial_id = cursor.lastrowid


    #2. Insert Treatments
    cursor.execute("""
        INSERT INTO treatments (trial_id, treatment_number, treatment_name, formulation_details, application_rate,
                               rate_unit)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (1, 1, "Control", "Untreated check", 0.00, "none"))

    control_treatment_id = cursor.lastrowid



    cursor.execute("""
        INSERT INTO treatments (trial_id, treatment_number, treatment_name, formulation_details, application_rate,
                               rate_unit)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (1, 2, "Treatment A", "Fungicide treatment", 1.25, "L/ha"))

    treatment_a_id = cursor.lastrowid

    conn.commit()

    #3. Insert Trial Sites
    cursor.execute("""
        INSERT INTO trial_sites (trial_id, site_name, latitude, longitude, soil_type,
        previous_crop, experimental_design, number_of_replicates)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (1, "North Field", 52.1234, -114.4567, "Loam", "Wheat", "RCBD", 4))

    site_id = cursor.lastrowid

    #4. Insert Plots
    # four plots for each of four replicates
    for replicate in range(1, 5):
        for plot_number in range(1,5):

            # Alternate treatments within each replicate
            if (plot_number + replicate) % 2 == 0:
                treatment_id = control_treatment_id
            else:
                treatment_id = treatment_a_id

            cursor.execute("""
                INSERT INTO PLOTS (site_id, plot_number, replicate_number, treatment_id, row_index, column_index)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (site_id, plot_number, replicate, treatment_id, replicate, plot_number))


    # Insert a set of assessment traits
    cursor.execute("""
        INSERT INTO assessment_traits (trial_id, trait_name, methodology, unit_of_measurement, data_type)
        VALUES (?, ?, ?, ?, ?)
    """, (trial_id, "Plant Height", "Measured from base to highest point", "cm", "numeric"))

    cursor.execute("""
        INSERT INTO assessment_traits (trial_id, trait_name, methodology, unit_of_measurement, data_type)
        VALUES (?, ?, ?, ?, ?)
    """, (trial_id, "Canopy Cover", "Visual field estimate", "%", "numeric"))

    cursor.execute("""
        INSERT INTO assessment_traits (trial_id, trait_name, methodology, unit_of_measurement, data_type)
        VALUES (?, ?, ?, ?, ?)
    """, (trial_id, "Yield", "Harvested plot weight", "kg/ha", "numeric"))

    # Insert some measurement records
    cursor.execute("""
        INSERT INTO assessment_data (trait_id, plot_id, numeric_value, assessment_date, text_value, collected_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (1, 1, 45.5, "2026-10-05", None, "A. Farmer", "Initial height assessment"))

    cursor.execute("""
        INSERT INTO assessment_data (trait_id, plot_id, numeric_value, assessment_date, text_value, collected_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (2, 1, 72.3, "2026-10-05", None, "A. Farmer", "Canopy cover check"))

    cursor.execute("""
        INSERT INTO assessment_data (trait_id, plot_id, numeric_value, assessment_date, text_value, collected_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (3, 1, 3010.0, "2026-12-15", None, "A. Farmer", "Final harvest yield"))

    conn.commit()
    conn.close()


def main():
    setup_tables()
    insert_trial_data()
    def display_plots():
        ...

    display_plots()

print("Database setup complete.")

if __name__ == "__main__":
    main() 
    



        

        



        



        










