from flask import Flask
from flask import request
from flask import Response
from flask import abort
from flask import jsonify
import pandas as pd

from base_iris_lab1 import add_dataset, build, train, score, new_model

app = Flask(__name__)
datasets = []


@app.route('/')
def index():
    return Response( '<h1>Hello, Extended Iris here!</h1>', status=201 )

@app.route('/iris/datasets', methods=['POST'])
def add_datasets():

    # Check if the 'train' field is present in the form data
    if 'train' not in request.form:
        return jsonify({"error": "Missing 'train' field in form data"}), 400

    # Get the data from the 'train' field
    train_data = None
    if 'train' in request.form:
        # If 'train' is a text field, use it directly
        train_data = request.form['train']

    # Check if data is present
    if not train_data:
        return jsonify({"error": "No data provided in 'train' field"}), 400

    try:
        # Split the plain text into lines
        lines = train_data.strip().split('\n')

        # Extract the header (first line)
        header = lines[0].strip().split(',')

        # Create a new dataset
        new_data = []

        # Process each line of data
        for line in lines[1:]:
            # Split the line into fields
            fields = line.strip().split(',')

            # Create a dictionary for the current row
            row_data = {}
            for i, field in enumerate(fields):
                
                try:
                    row_data[header[i]] = float(field)
                except ValueError:
                    row_data[header[i]] = field  

            # Add the row data to the new dataset
            new_data.append(row_data)

        # Append the new dataset to the global datasets list
        index = add_dataset(pd.DataFrame(new_data))

        # Return the index of the created dataset
        dataset_index = len(datasets) - 1
        return jsonify({"message": "Dataset added successfully", "index": index}), 201
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    

@app.route('/iris/model', methods=['POST'])
def add_model():
    # Check if the 'dataset' field is present in the form data
    if 'dataset' not in request.form:
        return jsonify({"error": "Missing 'dataset' field in form data"}), 400
    # Get the data index from the 'dataset' field
    dataset_index = request.form['dataset']
    # Check if the dataset index is valid
    dataset_index = int(dataset_index)
    print(dataset_index)
    # if dataset_index < 0 or dataset_index >= len(datasets):
    #     return jsonify({"error": "Invalid dataset index"}), 400
    # Build the model
    model_index = new_model(dataset_index)
    # Return the index of the created model
    return jsonify({"message": "Model created successfully", "index": model_index}), 201


@app.route('/iris/model/<int:n>', methods=['PUT'])
def retrain_model(n):
    dataset_index = request.args.get('dataset', type=int)
    # Retrain the model
    history = train(n, dataset_index)
    # Return the training history
    return jsonify({"message": "Model retrained successfully", "history": history}), 200



@app.route('/iris/model/<int:n>/score', methods=['GET'])
def score_model(n):

    # Get the fields from the query parameters
    fields = request.args.get('fields')
    if not fields:
        return jsonify({"error": "Missing fields in query parameters"}), 400

    # Split the fields into a list of values
    try:
        field_values = list(map(float, fields.split(',')))
    except ValueError:
        return jsonify({"error": "Invalid field values"}), 400

    # Check if the number of fields is correct
    if len(field_values) != 20:
        return jsonify({"error": "Exactly 20 fields are required"}), 400

    try:
        # Score the model
        result = score(n, field_values)
        return jsonify({"result": result}), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=4000)