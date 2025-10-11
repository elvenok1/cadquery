import cadquery as cq
from flask import Flask, request, send_file, jsonify
import tempfile
import os
from collections import Counter

# --- IMPORTS DE EXTENSIONES ---
from cq_gears.spur_gear import SpurGear
from cq_gears.helical_gear import HelicalGear
from cq_gears.bevel_gear import BevelGear
import cqkit

# --- ÁMBITO GLOBAL DE EJECUCIÓN, expone los módulos y clases ---
CQ_EXEC_SCOPE = {
    "cq": cq,
    "cqkit": cqkit,
    "SpurGear": SpurGear,
    "HelicalGear": HelicalGear,
    "BevelGear": BevelGear,
}

# --- FLASK ---
app = Flask(__name__)

# --- HEALTH CHECK ---
@app.route('/', methods=['GET'])
def health_check():
    return "CadQuery Service running.", 200

# --- ANALYZE STEP FILE ---
@app.route('/analyze', methods=['POST'])
def analyze_model():
    if 'step_file' not in request.files:
        return jsonify({"error": "No se encontró 'step_file'."}), 400

    step_file = request.files['step_file']
    input_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_input_file:
            step_file.save(temp_input_file.name)
            input_path = temp_input_file.name

        imported_wp = cq.importers.importStep(input_path)
        solids = imported_wp.solids().vals()
        if not solids:
            return jsonify({"error": "No se encontraron sólidos."}), 400

        analysis_report = {
            "file_name": step_file.filename,
            "summary": {"total_solids": len(solids)},
            "solids": [],
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
                "face_types": dict(face_types),
            }
            analysis_report["solids"].append(solid_info)

        return jsonify(analysis_report)

    except Exception as e:
        return jsonify({"error": f"Error al analizar: {str(e)}"}), 500
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)

# --- GENERAR PIEZA DESDE SCRIPT PYTHON ---
@app.route('/generate', methods=['POST'])
def generate_model():
    data = request.get_json()
    if not data or 'script' not in data:
        return jsonify({"error": "Se requiere JSON con 'script'"}), 400
    script_code = data['script']
    file_path = None
    try:
        local_scope = dict(CQ_EXEC_SCOPE)
        exec(script_code, local_scope)
        result_solid = None
        for val in local_scope.values():
            if isinstance(val, (cq.Workplane, cq.Shape)):
                result_solid = val
                break
        if result_solid is None:
            return jsonify({"error": "No se encontró objeto válido."}), 400
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_file:
            cq.exporters.export(result_solid, temp_file.name)
            file_path = temp_file.name
            return send_file(file_path, as_attachment=True, download_name='generated_model.step', mimetype='application/octet-stream')
    except Exception as e:
        return jsonify({"error": f"Error en script: {str(e)}"}), 500
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

# --- MODIFICAR PIEZA EXISTENTE CON SCRIPT ---
@app.route('/modify', methods=['POST'])
def modify_model():
    if 'step_file' not in request.files:
        return jsonify({"error": "No se encontró 'step_file'."}), 400
    if 'script' not in request.form:
        return jsonify({"error": "No se encontró 'script'."}), 400
    step_file = request.files['step_file']
    script_code = request.form['script']
    input_path, output_path = None, None
    try:
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_input_file:
            step_file.save(temp_input_file.name)
            input_path = temp_input_file.name
        imported_wp = cq.importers.importStep(input_path)
        local_scope = dict(CQ_EXEC_SCOPE)
        local_scope['model'] = imported_wp
        exec(script_code, local_scope)
        result_solid = None
        for val in local_scope.values():
            if isinstance(val, (cq.Workplane, cq.Shape)):
                result_solid = val
                break
        if result_solid is None:
            return jsonify({"error": "No se encontró objeto resultante."}), 400
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp_output_file:
            cq.exporters.export(result_solid, temp_output_file.name)
            output_path = temp_output_file.name
            return send_file(output_path, as_attachment=True, download_name='modified_model.step', mimetype='application/octet-stream')
    except Exception as e:
        return jsonify({"error": f"Error al modificar: {str(e)}"}), 500
    finally:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

# --- GENERAR ENGRANAJE RECTO DESDE PARÁMETROS ---
@app.route('/generate_gear', methods=['POST'])
def generate_gear():
    params = request.get_json()
    try:
        gear = SpurGear(**params)
        wp = cq.Workplane('XY').gear(gear)
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temp:
            cq.exporters.export(wp, temp.name)
            return send_file(temp.name, as_attachment=True, download_name='gear.step')
    except Exception as e:
        return jsonify({"error": f"Error generando engranaje: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
