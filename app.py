from flask import Flask, request, jsonify
import pandas as pd
import os

app = Flask(__name__)

CSV_FILE = 'datos_calidad_aire.csv'

if not os.path.exists(CSV_FILE):
    df = pd.DataFrame(columns=['valor_analogico', 'voltaje', 'calidad_aire'])
    df.to_csv(CSV_FILE, index=False)

@app.route('/data', methods=['POST'])
def receive_data():

    data = request.json
    print(data)

    if 'valor_analogico' not in data or 'voltaje' not in data or 'calidad_aire' not in data:
        return jsonify({'error': 'Datos incompletos'}), 400

    df = pd.read_csv(CSV_FILE)

    new_data = pd.DataFrame({
        'valor_analogico': [data['valor_analogico']],
        'voltaje': [data['voltaje']],
        'calidad_aire': [data['calidad_aire']]
    })

    df = pd.concat([df, new_data], ignore_index=True).dropna(axis=1, how='all')


    df.to_csv(CSV_FILE, index=False)

    return jsonify({'message': 'Datos guardados con éxito'}), 201


if __name__ == '__main__':
    app.run(host='192.168.1.117', port=5000)  