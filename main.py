from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
import io
import string
import unicodedata
import re

app = Flask(__name__)

# Preprocess function
def preprocess_column(list_):
    p = list()
    for el in list_:
        v = str(el).translate(str.maketrans('', '', string.punctuation)).lower()
        v = unicodedata.normalize('NFD', v)
        v = ''.join(c for c in v if unicodedata.category(c) != 'Mn')
        v = v.strip()
        v = re.sub(r'\s+', ' ', v)
        p.append(v)
    return p

# Store the processed DataFrame globally
processed_data = None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    global processed_data
    if 'files[]' not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist('files[]')
    list_df = []

    for file in files:
        try:
            # Read the Excel file using pandas
            df = pd.read_excel(file)
            df.columns = preprocess_column(list(df.columns))
            
            # Identify 'cpf' and 'pontuacao' columns
            cpf_column = [x for x in list(df.columns) if "cpf" in x]
            assert len(cpf_column) == 1
            df["cpf"] = preprocess_column(list(df[cpf_column[0]]))
            df["cpf"] = ["0" + el if len(el) == 10 else el for el in list(df["cpf"])]
            
            pont_column = [x for x in list(df.columns) if "pontuacao" in x]
            assert len(pont_column) == 1
            df[f"{file.filename}_pontuacao"] = preprocess_column(list(df[pont_column[0]]))
            
            # Keep only 'cpf' and 'pontuacao' columns
            df = df[["cpf", f"{file.filename}_pontuacao"]]
            
            list_df.append(df)
        
        except Exception as e:
            return jsonify({"error": f"Error reading {file.filename}: {e}"}), 400

    # Merge all DataFrames on 'cpf' using outer join
    processed_data = list_df[0]
    for df in list_df[1:]:
        processed_data = pd.merge(processed_data, df, on='cpf', how='outer')

    processed_data.fillna("", inplace=True)
    processed_data = processed_data.groupby('cpf').agg(list)
    processed_data.reset_index(inplace=True)

    return jsonify({"message": "Files uploaded and processed successfully!"})

@app.route('/download_results', methods=['GET'])
def download_results():
    if processed_data is None:
        return jsonify({"error": "No processed data available"}), 400
    
    # Save the result to a buffer as Excel file
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        processed_data.to_excel(writer, index=False, sheet_name="Processed Data")
    
    # Move the pointer to the beginning of the buffer
    buffer.seek(0)

    # Return the buffer as a file to be downloaded
    return send_file(buffer, as_attachment=True, download_name="processed_data.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == '__main__':
    app.run(debug=True)
