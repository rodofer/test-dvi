import json
import requests

# Configuración de URLs
PARSER_URL = "https://parser.rodofer.cl/traza"
MOTOR_URL = "https://motor.rodofer.cl/validar"  # Cambiar si tu motor semántico corre en otro puerto/servidor

# Definición de estilos ANSI (Colores y Negrita)
VERDE_NEGRITA = "\033[1;92m"
AMARILLO_NEGRITA = "\033[1;93m"
ROJO_NEGRITA = "\033[1;91m"
AZUL = "\033[94m"
CIAN_NEGRITA = "\033[1;96m"
RESET = "\033[0m"

def cargar_codigo_desde_archivo(ruta_archivo: str) -> str:
    """Lee el archivo de código fuente del estudiante."""
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        return f.read()

def ejecutar_depurador_interactivo(ruta_archivo: str):
    print(f"{AZUL}1. Leyendo archivo de código: {ruta_archivo}{RESET}")
    try:
        codigo = cargar_codigo_desde_archivo(ruta_archivo)
    except FileNotFoundError:
        print(f"{ROJO_NEGRITA}[Error]: No se encontró el archivo en la ruta '{ruta_archivo}'.{RESET}")
        return

    # Separamos el código en una lista de líneas para mostrarlas de forma estructurada
    lineas_codigo = codigo.splitlines()

    print(f"{AZUL}2. Solicitando traza al Parser API...{RESET}")
    response_parser = requests.post(PARSER_URL, json={"codigo": codigo})

    if response_parser.status_code != 200:
        print(f"{ROJO_NEGRITA}{response_parser.json()['detail']['mensaje']}{RESET}")
        return

    traza_json = response_parser.json()
    grafo_pasos = traza_json.get("@graph", [])

    print(f"\n{AZUL}=== INICIO DEL DEPURADOR VISUAL INTERACTIVO ==={RESET}")
    print(f"Total de pasos detectados en la traza: {len(grafo_pasos)}\n")

    aciertos = 0
    vejecutados = 0

    for paso in grafo_pasos:
        num_paso = paso.get("numeroPaso")
        linea_actual = paso.get("linea")

        # Filtramos los pasos que requieren interacción del estudiante
        if "modifica" in paso or "evalua" in paso:
            vejecutados += 1
            
            # --- MOSTRAR CÓDIGO FUENTE CON LA LÍNEA RESALTADA ---
            print(f"\n┌── Paso {num_paso} ─────────────────────────────")
            for idx, linea_texto in enumerate(lineas_codigo, start=1):
                if idx == linea_actual:
                    print(f"{CIAN_NEGRITA}  --> {idx:2d} | {linea_texto}{RESET}")
                else:
                    print(f"      {idx:2d} | {linea_texto}")
            print(f"└────────────────────────────────────────")

            # Definir texto del prompt según el tipo de paso
            if "modifica" in paso:
                var = paso["modifica"]["variable"]
                prompt_texto = f"¿Qué valor toma la variable '{var}'? -> "
            else:
                expr = paso["evalua"]["expresion"]
                prompt_texto = f"¿Cuál es el resultado de la condición '{expr}' (True/False)? -> "

            # Capturar la entrada del usuario
            entrada_usuario = input(prompt_texto).strip()

            # Conversión ligera de tipos básicos para que el JSON viaje estructurado,
            # dejando que el Motor maneje cualquier aviso o error semántico.
            entrada_lower = entrada_usuario.lower()
            if entrada_lower in ["true", "verdadero"]:
                respuesta_procesada = True
            elif entrada_lower in ["false", "falso"]:
                respuesta_procesada = False
            else:
                try:
                    respuesta_procesada = int(entrada_usuario)
                except ValueError:
                    respuesta_procesada = entrada_usuario

            # Enviar la validación al Motor Semántico
            payload_validacion = {
                "traza": traza_json,
                "numeroPaso": num_paso,
                "respuesta": respuesta_procesada
            }

            response_motor = requests.post(MOTOR_URL, json=payload_validacion)
            resultado_motor = response_motor.json()

            # El cliente imprime directamente los mensajes devueltos por el Motor
            if response_motor.status_code == 200:
                mensaje = resultado_motor.get('mensaje', 'Sin mensaje')
                if resultado_motor.get('correcto', False):
                    print(f"{VERDE_NEGRITA}✔ {mensaje}{RESET}\n")
                    aciertos += 1
                else:
                    # El aviso pedagógico, conceptual o de formato viene centralizado desde el Motor
                    print(f"{AMARILLO_NEGRITA}✖ {mensaje}{RESET}\n")
            else:
                mensaje = resultado_motor.get('detail', {}).get('mensaje', 'Error desconocido')
                print(f"{ROJO_NEGRITA}{mensaje}{RESET}\n")

    print(f"{AZUL}=== RESUMEN FINAL ==={RESET}")
    print(f"Completaste el ejercicio con {aciertos} aciertos de {vejecutados} pasos evaluados.")

if __name__ == "__main__":
    # Ruta de prueba de ejemplo
    ruta_prueba = "codigos/contador_suma.py"
    ejecutar_depurador_interactivo(ruta_prueba)
