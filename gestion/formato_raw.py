import re
from io import BytesIO

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.renderers import BrowsableAPIRenderer

from .mensajes_validacion import (
    FORMATOS_ACTA, FORMATOS_CARGA_MASIVA, FORMATOS_CLAVE, FORMATOS_COLEGIATURA, FORMATOS_CUENTA,
    FORMATOS_ESTADO_SISTEMA, FORMATOS_EXPEDIENTE,
)


class JSONLegibleParser(JSONParser):
    """Traduce errores de sintaxis antes de que los campos puedan validarse."""

    formatos_campos = {}

    def parse(self, stream, media_type=None, parser_context=None):
        cuerpo = stream.read() if self.formatos_campos else None
        if cuerpo is not None:
            stream = BytesIO(cuerpo)
        try:
            return super().parse(stream, media_type=media_type, parser_context=parser_context)
        except ParseError as error:
            if cuerpo is not None:
                posicion = re.search(r"\(char (\d+)\)", str(error))
                if posicion:
                    texto = cuerpo.decode("utf-8", errors="replace")
                    indice = int(posicion.group(1))
                    if indice < len(texto) and texto[indice].isalpha():
                        anterior = texto[:indice]
                        campo = re.search(
                            r'"(' + "|".join(self.formatos_campos) + r')"\s*:\s*$', anterior
                        )
                        if campo:
                            nombre = campo.group(1)
                            raise ParseError(
                                f"JSON mal formado. {nombre}: {self.formatos_campos[nombre]} "
                                "Escriba los textos y fechas entre comillas dobles."
                            ) from error
            raise ParseError(
                "JSON mal formado. Respete el formato JSON: use comillas dobles "
                "para textos y fechas y separe los campos con comas."
            ) from error


class JSONExpedienteParser(JSONLegibleParser):
    formatos_campos = FORMATOS_EXPEDIENTE


class JSONCuentaParser(JSONLegibleParser):
    formatos_campos = FORMATOS_CUENTA


class JSONActaParser(JSONLegibleParser):
    formatos_campos = FORMATOS_ACTA


class JSONColegiaturaParser(JSONLegibleParser):
    formatos_campos = FORMATOS_COLEGIATURA


class JSONEstadoSistemaParser(JSONLegibleParser):
    formatos_campos = FORMATOS_ESTADO_SISTEMA


class JSONClaveParser(JSONLegibleParser):
    formatos_campos = FORMATOS_CLAVE


class JSONCargaMasivaParser(JSONLegibleParser):
    formatos_campos = FORMATOS_CARGA_MASIVA

    def parse(self, stream, media_type=None, parser_context=None):
        limite = 14 * 1024 * 1024
        cuerpo = stream.read(limite + 1)
        if len(cuerpo) > limite:
            raise ParseError(
                "La carga masiva JSON no puede superar 14 MB en total. "
                "Para un lote más grande, use el formulario con archivos adjuntos."
            )
        return super().parse(BytesIO(cuerpo), media_type=media_type, parser_context=parser_context)


class AdjuntosMultiPartParser(MultiPartParser):
    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return super().parse(stream, media_type=media_type, parser_context=parser_context)
        except ParseError as error:
            if "boundary" in str(error).lower():
                raise ParseError(
                    "El cuerpo multipart/form-data no tiene un separador válido. "
                    "Use el formulario para adjuntar archivos; no pegue JSON como multipart."
                ) from error
            raise


class ActaBrowsableAPIRenderer(BrowsableAPIRenderer):
    def get_raw_data_form(self, data, view, method, request):
        formulario = super().get_raw_data_form(data, view, method, request)
        if formulario and method == "POST":
            formulario.fields["_content"].initial = (
                '{\n    "expediente": null,\n    "archivo_base64": ""\n}'
            )
        return formulario


class CargaMasivaBrowsableAPIRenderer(BrowsableAPIRenderer):
    def get_raw_data_form(self, data, view, method, request):
        formulario = super().get_raw_data_form(data, view, method, request)
        if formulario and method == "POST":
            formulario.fields["_content"].initial = (
                '{\n    "archivos": [\n        {\n            "expediente": null,\n'
                '            "nombre": "informe.pdf",\n            "contenido_base64": ""\n'
                '        }\n    ]\n}'
            )
        return formulario
