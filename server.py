from flask import Flask, request, jsonify, send_file
import mysql.connector
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask_cors import CORS
import io
import os
import base64

app = Flask(__name__)
CORS(app)

# ==================================================
def obtener_conexion():
    return mysql.connector.connect(
        host="localhost",
        user="",
        password="",
        database="iot_esp32",
        autocommit=True
    )

# ==================================================
@app.route('/datos', methods=['POST', 'GET'])
def recibir_datos():
    global estabilidad_global
    if request.method == 'POST':
        try:
            temperatura = request.form.get('temp')
            humedad = request.form.get('hum')
            nivel_agua = request.form.get('nivel_agua')
            estabilidad_raw = request.form.get('estabilidad')

            if not all([temperatura, humedad, nivel_agua]):
                return jsonify({"status": "error", "message": "Faltan datos"}), 400

            temperatura = float(temperatura)
            humedad = float(humedad)
            nivel_agua = float(nivel_agua)

            if estabilidad_raw in ['1', 'true', 'True', 'TRUE', 1, True]:
                estabilidad_global = "Estable ✅"
            else:
                estabilidad_global = "No estable ⚠️"

            conn = obtener_conexion()
            cursor = conn.cursor()
            sql = """
                INSERT INTO registro_ambiente 
                (temperatura, humedad, nivel_agua, tiempo) 
                VALUES (%s, %s, %s, NOW())
            """
            cursor.execute(sql, (temperatura, humedad, nivel_agua))
            cursor.close()
            conn.close()

            return jsonify({"status": "success", "message": "Datos guardados"}), 200

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    else:  # GET
        return jsonify({"mensaje": "Servidor IoT activo - POST /datos"}), 200

# ==================================================
@app.route('/dashboard')
def dashboard_completo():
    global estabilidad_global
    
    nombre_animal = request.args.get('animal', default=None, type=str) # Nombre de animal desde los parámetros
    
    # Valores por defecto si no se especifica animal
    rangos = {
        'min_temp': None, 'max_temp': None,
        'min_hum': None,  'max_hum': None
    }
    
    if nombre_animal:
        try:
            conn = obtener_conexion()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT minTemp, maxTemp, minHum, maxHum 
                FROM rangos_animales 
                WHERE Nombre = %s
            """, (nombre_animal.strip(),))
            resultado = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if resultado:
                rangos = {
                    'min_temp': float(resultado['minTemp']),
                    'max_temp': float(resultado['maxTemp']),
                    'min_hum':  float(resultado['minHum']),
                    'max_hum':  float(resultado['maxHum'])
                }
            else:
                # Animal no encontrado → se puede devolver advertencia o ignorar
                nombre_animal = None  
        except Exception as e:
            print(f"Error al buscar rangos del animal: {e}")
            nombre_animal = None

    try:
        conn = obtener_conexion()
        cursor = conn.cursor(dictionary=True)

        # 1. Último registro en tiempo real
        cursor.execute("""
            SELECT temperatura, humedad, nivel_agua, tiempo 
            FROM registro_ambiente 
            ORDER BY tiempo DESC 
            LIMIT 1
        """)
        ultimo = cursor.fetchone()

        if not ultimo:
            return jsonify({"status": "warning", "message": "Aún no hay datos"}), 404

        # 2. Datos para la gráfica del día actual
        hoy = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT minuto, avg_temperatura, avg_humedad, avg_nivel_agua
            FROM promedios_por_minuto 
            WHERE DATE(minuto) = %s
            ORDER BY minuto
        """, (hoy,))
        filas = cursor.fetchall()

        # Crear la gráfica con umbrales
        plt.figure(figsize=(12, 6.5))
        
        if filas:
            tiempos = [f['minuto'].strftime('%H:%M') for f in filas]
            temps = [f['avg_temperatura'] for f in filas]
            hums = [f['avg_humedad'] for f in filas]
            niveles = [f['avg_nivel_agua'] for f in filas]

            # Líneas principales
            plt.plot(tiempos, temps, label='Temperatura (°C)', color='#e74c3c', marker='o', linewidth=2.5, markersize=4)
            plt.plot(tiempos, hums, label='Humedad (%)', color='#3498db', marker='s', linewidth=2.5, markersize=4)
            plt.plot(tiempos, niveles, label='Nivel agua (%)', color='#2ecc71', marker='^', linewidth=2, alpha=0.8)

            # === Umbrales de temperatura ===
            if rangos['min_temp'] is not None:
                plt.axhline(y=rangos['min_temp'], color='#e74c3c', linestyle='--', linewidth=2, alpha=0.7, label=f'Temp mín ({rangos["min_temp"]}°C)')
                plt.axhline(y=rangos['max_temp'], color='#e74c3c', linestyle='--', linewidth=2, alpha=0.7, label=f'Temp máx ({rangos["max_temp"]}°C)')
            
            # === Umbrales de humedad ===
            if rangos['min_hum'] is not None:
                plt.axhline(y=rangos['min_hum'], color='#3498db', linestyle=':', linewidth=2, alpha=0.7, label=f'Hum mín ({rangos["min_hum"]}%)')
                plt.axhline(y=rangos['max_hum'], color='#3498db', linestyle=':', linewidth=2, alpha=0.7, label=f'Hum máx ({rangos["max_hum"]}%)')

            plt.xticks(rotation=45, ha='right')
            plt.grid(True, alpha=0.3)
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)  # Leyenda fuera para más espacio
            plt.tight_layout()

        # Título con el animal si está seleccionado
        titulo = f'Reporte diario - {hoy}'
        if nombre_animal:
            titulo += f' | {nombre_animal}'
        plt.title(titulo, fontsize=16, fontweight='bold')
        plt.xlabel('Hora')
        plt.ylabel('Valor')

        # Convertir a Base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        cursor.close()
        conn.close()

        # Respuesta final
        respuesta = {
            "status": "success",
            "animal_seleccionado": nombre_animal,
            "rangos_aplicados": rangos if nombre_animal else None,
            "actual": {
                "temperatura": round(ultimo['temperatura'], 2),
                "humedad": round(ultimo['humedad'], 2),
                "nivel_agua": round(ultimo['nivel_agua'], 2),
                "hora": ultimo['tiempo'].strftime('%H:%M:%S'),
                "estabilidad": estabilidad_global
            },
            "grafica_base64": f"data:image/png;base64,{img_base64}",
            "fecha_grafica": hoy
        }
        
        return jsonify(respuesta)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================================================
@app.route('/promedios_por_minuto', methods=['GET'])
def historia_dias():
    try:
        conn = obtener_conexion()
        cursor = conn.cursor(dictionary=True)

        # Tomamos el ÚLTIMO minuto que tenga datos
        query = """
            SELECT
                minuto,
                avg_temperatura AS temp,
                avg_humedad AS hum,
                avg_nivel_agua AS nivel,
                conteo_registros
            FROM promedios_por_minuto
            WHERE avg_temperatura IS NOT NULL
               OR avg_humedad IS NOT NULL
               OR avg_nivel_agua IS NOT NULL
            ORDER BY minuto DESC
            LIMIT 1
        """
        cursor.execute(query)
        ultimo = cursor.fetchone()

        cursor.close()
        conn.close()

        if not ultimo:
            return jsonify({
                "status": "success",
                "message": "Aún no hay datos promedio",
                "ultimo_registro": None
            })

        return jsonify({
            "status": "success",
            "ultimo_registro": {
                "fecha_hora": ultimo['minuto'].strftime('%Y-%m-%d %H:%M'),
                "temperatura": round(ultimo['temp'], 2) if ultimo['temp'] else None,
                "humedad": round(ultimo['hum'], 2) if ultimo['hum'] else None,
                "nivel_agua": round(ultimo['nivel'], 2) if ultimo['nivel'] else None,
                "registros_en_minuto": ultimo['conteo_registros']
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
