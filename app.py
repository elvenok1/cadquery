import cadquery as cq
from flask import Flask, request, send_file, jsonify
import tempfile
import os
from collections import Counter

# Inicializar la aplicación Flask
app = Flask(__name__)

# --- ENDPOINT PARA HEALTH CHECK ---
@app.route('/', methods=['GET'])
def health_check():
    """Responde a los chequeos de salud de la plataforma de despliegue."""
    return "CadQuery Service is running.", 200

# --- NUEVO ENDPOINT PARA ANALIZAR UN ARCHIVO .STEP ---
@app.route('/analyze', methods=['POST'])
def analyze_model():
    """
    Recibe un archivo .step y devuelve un desglose de su contenido en JSON.
    """
    if 'step_file' not in request.files:
        return jsonify({"error": "No se encontró el archivo 'step_file' en la petición."}), 400

    step_file = request.files['step_file']
    input_path = None

    try:
        # Guardar el STEP recibido en un archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_input_file:
            step_file.save(temp_input_file.name)
            input_path = temp_input_file.name

        # Cargar el modelo STEP. importStep devuelve un objeto Shape.
        model_shape = cq.importers.importStep(input_path)

        # Extraer los sólidos del modelo
        solids = model_shape.Solids()
        
        analysis_report = {
            "file_name": step_file.filename,
            "summary": {
                "total_solids": len(solids),
            },
            "solids": []
        }

        # Analizar cada sólido encontrado en el archivo
        for i, solid in enumerate(solids):
            faces = solid.Faces()
            bounds = solid.BoundingBox()
            
            # Contar los tipos de caras (plana, cilíndrica, etc.)
            face_types = Counter(f.geomType() for f in faces)

            solid_info = {
                "solid_index": i + 1,
                "volume": solid.Volume(),
                "center_of_mass": {
                    "x": solid.Center().x,
                    "y": solid.Center().y,
                    "z": solid.Center().z,
                },
                "bounding_box": {
                    "length_x": bounds.xlen,
                    "length_y": bounds.ylen,
                    "length_z": bounds.zlen,
                },
                "topology": {
                    "faces": len(faces),
                    "edges": len(solid.Edges()),
                    "vertices": len(solid.Vertices()),
                },
                "face_types": dict(face_types)
            }
            analysis_report["solids"].append(solid_info)

        return jsonify(analysis_report)

    except Exception as e:
        return jsonify({"error": f"Error al analizar el archivo STEP: {str(e)}"}), 500
    finally:
        # Limpiar el archivo temporal
        if input_path and os.path.exists(input_path):
            os.remove(input_path)


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
    file_path = None
    
    try:
        local_scope = {}
        exec(script_code, {"cq": cq}, local_scope)

        result_solid = None
        for val in local_scope.values():
            if isinstance(val, (cq.Workplane, cq.Shape)):
                result_solid = val
                break
        
        if result_solid is None:
            return jsonify({"error": "No se encontró un objeto 'Workplane' o 'Shape' de CadQuery en el resultado del script."}), 400

        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_file:
            file_path = temp_file.name
            cq.exporters.export(result_solid, file_path)
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name='generated_model.step',
            mimetype='application/octet-stream'
        )

    except Exception as e:
        return jsonify({"error": f"Error al ejecutar el script de CadQuery: {str(e)}"}), 500
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

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
    input_path = None
    output_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_input_file:
            step_file.save(temp_input_file.name)
            input_path = temp_input_file.name

        imported_model = cq.importers.importStep(input_path)
        
        local_scope = {'model': imported_model}
        exec(script_code, {"cq": cq}, local_scope)

        result_solid = None
        for val in local_scope.values():
            if isinstance(val, (cq.Workplane, cq.Shape)):
                result_solid = val
                break
        
        if result_solid is None:
            return jsonify({"error": "No se encontró un objeto resultante en el script de modificación."}), 400

        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_output_file:
            output_path = temp_output_file.name
            cq.exporters.export(result_solid, output_path)

        return send_file(
            output_path,
            as_attachment=True,
            download_name='modified_model.step',
            mimetype='application/octet-stream'
        )

    except Exception as e:
        return jsonify({"error": f"Error al modificar el modelo: {str(e)}"}), 500
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
