import cadquery as cq
from flask import Flask, request, send_file, jsonify
import tempfile
import os

# Inicializar la aplicación Flask
app = Flask(__name__)

# --- Endpoint para GENERAR una nueva pieza desde código Python ---
@app.route('/generate', methods=['POST'])
def generate_model():
    """
    Recibe un JSON con 'script' y genera un modelo 3D.
    Devuelve el archivo .STEP resultante.
    """
    data = request.get_json()
    if not data or 'script' not in data:
        return jsonify({"error": "Se requiere un JSON con la clave 'script'"}), 400

    script_code = data['script']
    
    try:
        # Espacio de nombres para ejecutar el script de forma segura
        local_scope = {}
        exec(script_code, {"cq": cq}, local_scope)

        # Buscar el objeto resultado en el scope local
        result_solid = None
        for val in local_scope.values():
            if isinstance(val, cq.Workplane):
                result_solid = val
                break
        
        if result_solid is None:
            return jsonify({"error": "No se encontró un objeto 'Workplane' de CadQuery en el resultado del script."}), 400

        # Crear un archivo temporal para guardar el STEP
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_file:
            file_path = temp_file.name
            cq.exporters.export(result_solid, file_path)
        
        print(f"Modelo generado y guardado en: {file_path}")

        # Enviar el archivo al cliente y luego eliminarlo
        return send_file(
            file_path,
            as_attachment=True,
            download_name='generated_model.step',
            mimetype='application/octet-stream'
        )

    except Exception as e:
        return jsonify({"error": f"Error al ejecutar el script de CadQuery: {str(e)}"}), 500

# --- Endpoint para MODIFICAR un archivo .STEP existente ---
@app.route('/modify', methods=['POST'])
def modify_model():
    """
    Recibe un archivo .STEP y un script de modificación.
    Aplica el script al modelo y devuelve el .STEP modificado.
    """
    if 'step_file' not in request.files:
        return jsonify({"error": "No se encontró el archivo 'step_file' en la petición."}), 400
    
    if 'script' not in request.form:
        return jsonify({"error": "No se encontró el 'script' de modificación en el formulario."}), 400

    step_file = request.files['step_file']
    script_code = request.form['script']

    try:
        # Guardar el STEP recibido en un archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_input_file:
            step_file.save(temp_input_file.name)
            input_path = temp_input_file.name

        # Cargar el modelo STEP en CadQuery
        imported_model = cq.importers.importStep(input_path)

        # Espacio de nombres para ejecutar el script de modificación
        # El modelo cargado estará disponible como la variable 'model'
        local_scope = {'model': imported_model}
        exec(script_code, {"cq": cq}, local_scope)

        # Buscar el objeto resultado
        result_solid = None
        for val in local_scope.values():
            if isinstance(val, cq.Workplane):
                result_solid = val
                break
        
        if result_solid is None:
            return jsonify({"error": "No se encontró un objeto 'Workplane' resultante en el script de modificación."}), 400

        # Exportar el modelo modificado a otro archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_output_file:
            output_path = temp_output_file.name
            cq.exporters.export(result_solid, output_path)

        # Limpiar el archivo de entrada
        os.remove(input_path)
        
        # Devolver el nuevo archivo
        return send_file(
            output_path,
            as_attachment=True,
            download_name='modified_model.step',
            mimetype='application/octet-stream'
        )

    except Exception as e:
        return jsonify({"error": f"Error al modificar el modelo: {str(e)}"}), 500

# Iniciar el servidor
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)