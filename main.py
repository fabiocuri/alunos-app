from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
import io
import string
import unicodedata
import re
import os

app = Flask(__name__)

# Define the folder path for file uploads
UPLOAD_FOLDER = "Forms/AV1"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Utility function to ensure folder exists
def ensure_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)


# General preprocessing function
def preprocess_generic(data, upper=False, remove_punct=True):
    processed = []
    for value in data:
        text = str(value)
        if remove_punct:
            text = text.translate(str.maketrans("", "", string.punctuation))
        if upper:
            text = text.upper()
        else:
            text = text.lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        text = re.sub(r"\s+", " ", text.strip())
        processed.append(text)
    return processed


# Preprocess CPF column specifically (no special characters but keep lowercase)
def preprocess_cpf(data):
    return [str(x).translate(str.maketrans("", "", string.punctuation)).lower().rstrip().lstrip() for x in data]


# Store the processed DataFrame globally
processed_data = None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_files():
    global processed_data
    if "files[]" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist("files[]")
    uploaded_dataframes = []

    for file in files:
        try:
            # Save the uploaded file
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)

            # Load and preprocess the Excel file
            df = pd.read_excel(file_path)

            # Normalize column names
            df.columns = preprocess_generic(df.columns)

            # Process CPF column
            cpf_column = [col for col in df.columns if "cpf" in col]
            if len(cpf_column) != 1:
                raise ValueError("Exactly one CPF column is required.")
            df["cpf"] = preprocess_cpf(df[cpf_column[0]])

            # Add missing leading zeroes for CPF with 10 digits
            df["cpf"] = df["cpf"].apply(lambda x: "0" + x if len(x) == 10 else x)

            # Process "nome" column
            name_column = [col for col in df.columns if "seu nome" in col]
            if len(name_column) != 1:
                raise ValueError("Exactly one 'seu nome' column is required.")
            df[f"{file.filename}_nome"] = preprocess_generic(df[name_column[0]], upper=True)

            # Process "pontuação" column
            pont_column = [col for col in df.columns if "pontuacao" in col]
            if len(pont_column) != 1:
                raise ValueError("Exactly one 'pontuação' column is required.")
            df[f"{file.filename}_pontuacao"] = preprocess_generic(df[pont_column[0]])

            # Keep only relevant columns
            df = df[["cpf", f"{file.filename}_pontuacao", f"{file.filename}_nome"]]
            uploaded_dataframes.append(df)

        except Exception as e:
            return jsonify({"error": f"Error processing file {file.filename}: {str(e)}"}), 400

    # Merge all DataFrames on 'cpf' using outer join
    processed_data = uploaded_dataframes[0]
    for df in uploaded_dataframes[1:]:
        processed_data = pd.merge(processed_data, df, on="cpf", how="outer")

    # Clean up processed data
    processed_data.fillna("", inplace=True)
    processed_data = processed_data.groupby("cpf").agg(list).reset_index()

    # Consolidate all "nome" columns into one
    nome_columns = [col for col in processed_data.columns if col.endswith("_nome")]
    processed_data["nome"] = processed_data[nome_columns].apply(
        lambda row: list({item for sublist in row for item in sublist if item}), axis=1
    )

    # Remove individual "_nome" columns
    processed_data.drop(columns=nome_columns, inplace=True)

    # Remove empty lists and deduplicate other columns
    for col in processed_data.columns:
        if col != "cpf":
            processed_data[col] = processed_data[col].apply(
                lambda x: "" if not x else (x[0] if len(set([val for val in x if val])) == 1 else ", ".join(list(set([val for val in x if val]))))
            )

    processed_data = processed_data.sort_values(by="nome")

    return jsonify({"message": "Files uploaded and processed successfully!"})


@app.route("/download_results", methods=["GET"])
def download_results():
    if processed_data is None:
        return jsonify({"error": "No processed data available"}), 400

    # Save the result to an Excel file in memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        processed_data.to_excel(writer, index=False, sheet_name="Processed Data")
    buffer.seek(0)

    # Send the file for download
    return send_file(
        buffer,
        as_attachment=True,
        download_name="processed_data.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=True)
