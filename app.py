import cadquery as cq
from flask import Flask, request, send_file, jsonify
import tempfile
import os
from collections import Counter

# --- NUEVOS IMPORTS CORREGIDOS ---
# Importa las clases desde sus módulos específicos dentro de cq_gears
from cq_gears.spur_gear import SpurGear
from cq_gears.helical_gear import HelicalGear
from cq_gears.bevel_gear import BevelGear
import cqkit

# Inicializar la aplicación Flask
app = Flask(__name__)

# --- ÁMBITO GLOBAL PARA SCRIPTS (SIN CAMBIOS, PERO AHORA FUNCIONARÁ) ---
CQ_EXEC_SCOPE = {
    "cq": cq,
    "cqkit": cqkit,
    "SpurGear": SpurGear,
    "HelicalGear": HelicalGear,
    "BevelGear": BevelGear,
}


# --- ENDPOINT PARA HEALTH CHECK ---
@app.route('/', methods=['GET'])
def health_check():
    """Responde a los chequeos de salud de la plataforma de despliegue."""
    return "CadQuery Service is running.", 200

# --- ENDPOINT PARA ANALIZAR UN ARCHIVO .STEP (sin cambios) ---
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
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_input_file:
            step_file.save(temp_input_file.name)
            input_path = temp_input_file.name

        imported_wp = cq.importers.importStep(input_path)
        solids = imported_wp.solids().vals()
        
        if not solids:
            return jsonify({"error": "No se encontraron sólidos en el archivo STEP proporcionado."}), 400
        
        analysis_report = {
            "file_name": step_file.filename,
            "summary": {
                "total_solids": len(solids),
            },
            "solids": []
        }

        for i, solid_shape in enumerate(solids):
            faces = solid_shape.Faces()
            bounds = solid_shape.BoundingBox()
            face_types = Counter(f.geomType() for f in faces)

            solid_info = {
                "solid_index": i + 1,
                "volume": solid_shape.Volume(),
                "center_of_mass": {
                    "x": solid_shape.Center().x,
                    "y": solid_shape.Center().y,
                    "z": solid_shape.Center().z,
                },
                "bounding_box": {
                    "length_x": bounds.xlen,
                    "length_y": bounds.ylen,
                    "length_z": bounds.zlen,
                },
                "topology": {
                    "faces": len(faces),
                    "edges": len(solid_shape.Edges()),
                    "vertices": len(solid_shape.Vertices()),
                },
                "face_types": dict(face_types)
            }
            analysis_report["solids"].append(solid_info)

        return jsonify(analysis_report)

    except Exception as e:
        return jsonify({"error": f"Error al analizar el archivo STEP: {str(e)}"}), 500
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)


# --- Endpoint para GENERAR una nueva pieza (sin cambios en la lógica) ---
@app.route('/generate', methods=['POST'])
def generate_model():
    data = request.get_json()
    if not data or 'script' not in data:
        return jsonify({"error": "Se requiere un JSON con la clave 'script'"}), 400
    script_code = data['script']
    file_path = None
    try:
        local_scope = {}
        exec(script_code, CQ_EXEC_SCOPE, local_scope)
        
        result_solid = None
        if 'result' in local_scope:
            result_solid = local_scope['result']
        else:
            for val in local_scope.values():
                if isinstance(val, (cq.Workplane, cq.Shape)):
                    result_solid = val
                    break
        
        if result_solid is None:
            return jsonify({"error": "No se encontró un objeto 'Workplane' o 'Shape' en la variable 'result' del script."}), 400
        
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_file:
            file_path = temp_file.name
            cq.exporters.export(result_solid, file_path)
            
        return send_file(file_path, as_attachment=True, download_name='generated_model.step', mimetype='application/octet-stream')
    except Exception as e:
        return jsonify({"error": f"Error al ejecutar el script de CadQuery: {str(e)}"}), 500
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

# --- Endpoint para MODIFICAR un archivo .STEP (sin cambios en la lógica) ---
@app.route('/modify', methods=['POST'])
def modify_model():
    if 'step_file' not in request.files:
        return jsonify({"error": "No se encontró el archivo 'step_file' en la petición."}), 400
    if 'script' not in request.form:
        return jsonify({"error": "No se encontró el 'script' de modificación en el formulario."}), 400
    
    step_file = request.files['step_file']
    script_code = request.form['script']
    input_path, output_path = None, None
    
    try:
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_input_file:
            step_file.save(temp_input_file.name)
            input_path = temp_input_file.name
            
        imported_wp = cq.importers.importStep(input_path)
        local_scope = {'model': imported_wp}
        exec(script_code, CQ_EXEC_SCOPE, local_scope)
        
        result_solid = None
        if 'result' in local_scope:
            result_solid = local_scope['result']
        else:
             for val in local_scope.values():
                if isinstance(val, (cq.Workplane, cq.Shape)) and val is not imported_wp:
                    result_solid = val
                    break

        if result_solid is None:
            return jsonify({"error": "No se encontró un objeto resultante en la variable 'result' del script de modificación."}), 400
        
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_output_file:
            output_path = temp_output_file.name
            cq.exporters.export(result_solid, output_path)
            
        return send_file(output_path, as_attachment=True, download_name='modified_model.step', mimetype='application/octet-stream')
    except Exception as e:
        return jsonify({"error": f"Error al modificar el modelo: {str(e)}"}), 500
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
