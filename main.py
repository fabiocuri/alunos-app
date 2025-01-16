from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
import io
import random

app = Flask(__name__)

# List of example DataFrames
df_list = [
    pd.DataFrame({"A": range(10), "B": range(10, 20)}),
    pd.DataFrame({"X": range(5), "Y": range(5, 10)}),
    pd.DataFrame({"P": range(3), "Q": range(3, 6)})
]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files[]' not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist('files[]')
    results = []

    for file in files:
        try:
            # Read the Excel file using pandas
            df = pd.read_excel(file)
            print(df)
            results.append(df)
        except Exception as e:
            results.append(f"Error reading {file.filename}: {e}")

    return jsonify({"results": results})

@app.route('/download_random', methods=['GET'])
def download_random_dataframe():
    # Select a random DataFrame from the list
    df_random = random.choice(df_list)
    
    # Save it to a buffer
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_random.to_excel(writer, index=False, sheet_name="Random DataFrame")
    
    # Move the pointer to the beginning of the buffer
    buffer.seek(0)

    # Return the buffer as a file to be downloaded
    return send_file(buffer, as_attachment=True, download_name="random_dataframe.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == '__main__':
    app.run(debug=True)
