import sys

import requests

# Configuración de URLs
PARSER_URL = "https://parser.rodofer.cl/traza"
MOTOR_URL = "https://motor.rodofer.cl/validar"
TIMEOUT = 10  # segundos por solicitud

# Errores del motor que se deben al formato de la respuesta: se vuelve a preguntar
ERRORES_DE_FORMATO = {"TipoDeRespuestaInvalido", "SolicitudInvalida"}

# Definición de estilos ANSI (Colores y Negrita)
VERDE_NEGRITA = "\033[1;92m"
AMARILLO_NEGRITA = "\033[1;93m"
ROJO_NEGRITA = "\033[1;91m"
AZUL = "\033[94m"
CIAN_NEGRITA = "\033[1;96m"
TENUE = "\033[2m"
RESET = "\033[0m"

PALABRAS_VERDADERO = {"true", "verdadero"}
PALABRAS_FALSO = {"false", "falso"}


class EntradaInvalidaError(ValueError):
    pass


class ErrorDeServicio(Exception):
    pass


def interpretar_valor(texto: str) -> int:
    try:
        return int(texto)
    except ValueError as e:
        raise EntradaInvalidaError("Escribe un número entero") from e


def interpretar_verdad(texto: str) -> bool:
    texto = texto.strip().lower()
    if texto in PALABRAS_VERDADERO:
        return True
    if texto in PALABRAS_FALSO:
        return False
    raise EntradaInvalidaError("Escribe verdadero o falso")


def llamar(url: str, cuerpo: dict) -> tuple[int, dict]:
    """POST a una API. Devuelve (código HTTP, JSON) o lanza ErrorDeServicio."""
    try:
        respuesta = requests.post(url, json=cuerpo, timeout=TIMEOUT)
    except requests.Timeout as e:
        raise ErrorDeServicio(f"{url} no respondió en {TIMEOUT} s") from e
    except requests.RequestException as e:
        raise ErrorDeServicio(f"No se pudo conectar con {url}: {e}") from e
    try:
        return respuesta.status_code, respuesta.json()
    except ValueError as e:
        raise ErrorDeServicio(
            f"{url} respondió {respuesta.status_code} sin JSON: {respuesta.text[:200]!r}"
        ) from e


def detalle_del_error(datos: dict) -> tuple[str, str]:
    detalle = datos.get("detail", {}) if isinstance(datos, dict) else {}
    if not isinstance(detalle, dict):
        return "Desconocido", str(detalle)
    return detalle.get("tipo", "Desconocido"), detalle.get("mensaje", "Sin mensaje")


def cargar_codigo_desde_archivo(ruta_archivo: str) -> str:
    """Lee el archivo de código fuente del estudiante."""
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        return f.read()


def mostrar_paso(num_paso: int, linea_actual: int, lineas_codigo: list, memoria: dict):
    print(f"\n┌── Paso {num_paso} ─────────────────────────────")
    for idx, linea_texto in enumerate(lineas_codigo, start=1):
        if idx == linea_actual:
            print(f"{CIAN_NEGRITA}  --> {idx:2d} | {linea_texto}{RESET}")
        else:
            print(f"      {idx:2d} | {linea_texto}")
    print("├── Memoria ─────────────────────────────")
    if memoria:
        print("  " + ", ".join(f"{var} = {valor}" for var, valor in memoria.items()))
    else:
        print("  (vacía)")
    print("└────────────────────────────────────────")


def formato(valor) -> str:
    if valor is True:
        return "verdadero"
    if valor is False:
        return "falso"
    return str(valor)


def pedir_respuesta(paso: dict):
    """Pregunta hasta que la entrada tenga el tipo que el paso necesita."""
    if "modifica" in paso:
        var = paso["modifica"]["variable"]
        prompt_texto = f"¿Qué valor toma la variable '{var}'? -> "
        interpretar = interpretar_valor
    else:
        expr = paso["evalua"]["expresion"]
        prompt_texto = f"¿La condición '{expr}' es verdadera o falsa? -> "
        interpretar = interpretar_verdad
    while True:
        try:
            return interpretar(input(prompt_texto))
        except EntradaInvalidaError as e:
            print(f"{ROJO_NEGRITA}{e}{RESET}")


def validar_paso(traza_json: dict, paso: dict) -> dict:
    """Pide la respuesta y la valida con el motor. Repite si el error es de formato."""
    while True:
        respuesta = pedir_respuesta(paso)
        status, datos = llamar(MOTOR_URL, {
            "traza": traza_json,
            "numeroPaso": paso["numeroPaso"],
            "respuesta": respuesta,
        })
        if status == 200:
            return datos
        tipo, mensaje = detalle_del_error(datos)
        if status == 422 and tipo in ERRORES_DE_FORMATO:
            print(f"{ROJO_NEGRITA}{mensaje}{RESET} {TENUE}[{tipo}]{RESET}")
            continue
        raise ErrorDeServicio(f"Motor respondió {status} {tipo}: {mensaje}")


def ejecutar_depurador_interactivo(ruta_archivo: str):
    print(f"{AZUL}1. Leyendo archivo de código: {ruta_archivo}{RESET}")
    try:
        codigo = cargar_codigo_desde_archivo(ruta_archivo)
    except FileNotFoundError:
        print(f"{ROJO_NEGRITA}[Error]: No se encontró el archivo en la ruta '{ruta_archivo}'.{RESET}")
        return

    lineas_codigo = codigo.splitlines()

    print(f"{AZUL}2. Solicitando traza al Parser API...{RESET}")
    try:
        status, traza_json = llamar(PARSER_URL, {"codigo": codigo})
    except ErrorDeServicio as e:
        print(f"{ROJO_NEGRITA}[Error]: {e}{RESET}")
        return
    if status != 200:
        tipo, mensaje = detalle_del_error(traza_json)
        print(f"{ROJO_NEGRITA}{mensaje}{RESET} {TENUE}[{status} {tipo}]{RESET}")
        return

    grafo_pasos = traza_json.get("@graph", [])

    print(f"\n{AZUL}=== INICIO DEL DEPURADOR VISUAL INTERACTIVO ==={RESET}")
    print(f"Total de pasos detectados en la traza: {len(grafo_pasos)}\n")

    aciertos = 0
    evaluados = 0
    memoria = {}

    try:
        for paso in grafo_pasos:
            mostrar_paso(paso["numeroPaso"], paso["linea"], lineas_codigo, memoria)
            resultado = validar_paso(traza_json, paso)
            evaluados += 1

            mensaje = resultado.get("mensaje", "Sin mensaje")
            if resultado.get("correcto") is True:
                print(f"{VERDE_NEGRITA}✔ {mensaje}{RESET}\n")
                aciertos += 1
            else:
                print(f"{AMARILLO_NEGRITA}✖ {mensaje}{RESET}")
                print(f"  Valor correcto: {formato(resultado.get('valorEsperado'))} "
                      f"{TENUE}[{resultado.get('tipoError')}]{RESET}\n")

            # Se continúa siempre con el valor correcto de la traza experta
            if "modifica" in paso:
                memoria[paso["modifica"]["variable"]] = paso["modifica"]["valorNuevo"]
    except ErrorDeServicio as e:
        print(f"\n{ROJO_NEGRITA}[Error]: {e}{RESET}")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{AZUL}Ejecución interrumpida.{RESET}")

    print(f"{AZUL}=== RESUMEN FINAL ==={RESET}")
    print(f"Respondiste {aciertos} de {evaluados} pasos correctamente "
          f"(la traza tiene {len(grafo_pasos)} pasos).")


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "codigos/contador_suma.py"
    ejecutar_depurador_interactivo(ruta)
