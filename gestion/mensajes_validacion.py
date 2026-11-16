FORMATO_ANIO_EGRESO = "Ingrese un año de egreso entero entre 2020 y 2050."
FORMATO_SEMESTRE_EGRESO = "El semestre de egreso debe ser 1 o 2."
FORMATO_FECHA_EXAMEN = "Use una fecha válida en formato AAAA-MM-DD, por ejemplo 2026-11-10."
FORMATO_NOTA_EXAMEN = "Ingrese una nota numérica entre 1,0 y 7,0 con un decimal."
FORMATO_ROL = "El rol debe ser administrador, coordinador o estudiante."
FORMATO_BOOLEANO = "Use true o false (sin comillas)."
FORMATO_ESTADO_COLEGIATURA = "El estado debe ser al-dia, no-al-dia o sin-informar."
FORMATO_EXPEDIENTE_ID = "Indique un ID de expediente entero existente."
FORMATO_EMAIL = "Ingrese un correo electrónico válido, por ejemplo nombre@dominio.cl."

FORMATOS_EXPEDIENTE = {
    "nombre": "Ingrese un nombre de persona entre comillas.",
    "rut": "Ingrese un RUT válido como texto, por ejemplo 12.345.678-5.",
    "anio_egreso": FORMATO_ANIO_EGRESO,
    "semestre_egreso": FORMATO_SEMESTRE_EGRESO,
    "fecha_examen": FORMATO_FECHA_EXAMEN,
    "nota_examen": FORMATO_NOTA_EXAMEN,
    "profesor_guia": "Ingrese el nombre del profesor guía entre comillas.",
    "informante_1": "Ingrese el nombre del primer informante entre comillas.",
    "informante_2": "Ingrese el nombre del segundo informante entre comillas.",
    "informante_adicional": "Ingrese el nombre del informante adicional entre comillas.",
}

FORMATOS_CUENTA = {
    "email": FORMATO_EMAIL,
    "password": "Ingrese la contraseña como texto entre comillas.",
    "nombre": "Ingrese un nombre de persona entre comillas.",
    "rol": FORMATO_ROL,
    "activo": FORMATO_BOOLEANO,
    "expediente": FORMATO_EXPEDIENTE_ID,
}

FORMATOS_ACTA = {
    "expediente": FORMATO_EXPEDIENTE_ID,
    "archivo_base64": "Ingrese el contenido Base64 del PDF entre comillas.",
}

FORMATOS_COLEGIATURA = {
    "estado_nuevo": FORMATO_ESTADO_COLEGIATURA,
    "observacion": "Ingrese la observación como texto entre comillas.",
}

FORMATOS_ESTADO_SISTEMA = {
    "mantenimiento": FORMATO_BOOLEANO,
    "mensaje": "Ingrese el mensaje como texto entre comillas.",
}

FORMATOS_CLAVE = {
    "clave_actual": "Ingrese la contraseña actual como texto entre comillas.",
    "clave_nueva": "Ingrese la contraseña nueva como texto entre comillas.",
}

FORMATOS_CARGA_MASIVA = {
    "archivos": "Envíe una lista de archivos con expediente, nombre y contenido_base64.",
    "expediente": FORMATO_EXPEDIENTE_ID,
    "nombre": "Ingrese el nombre del archivo con su extensión entre comillas.",
    "contenido_base64": "Ingrese el contenido Base64 del archivo entre comillas.",
}
