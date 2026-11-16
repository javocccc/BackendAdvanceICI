import base64
import binascii
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import EmailValidator, MaxLengthValidator, MinLengthValidator
from django.db import transaction
from rest_framework import serializers

from .documentos import EXTENSIONES, MAX_ARCHIVOS, MAX_BYTES_ARCHIVO, validar_documento
from .mensajes_validacion import (
    FORMATO_ANIO_EGRESO, FORMATO_FECHA_EXAMEN,
    FORMATO_NOTA_EXAMEN, FORMATO_SEMESTRE_EGRESO,
    FORMATO_BOOLEANO, FORMATO_EMAIL, FORMATO_ESTADO_COLEGIATURA, FORMATO_ROL,
)
from .models import Acta, CambioColegiatura, ConfiguracionSistema, DocumentoExpediente, Expediente, PerfilUsuario, RegistroAuditoria
from .rut import normalizar_rut


class CamposJsonEsperadosMixin:
    """Informa las claves desconocidas en JSON y formularios de escritura."""

    mensajes_campos = {}

    def get_fields(self):
        campos = super().get_fields()
        for nombre, mensajes in self.mensajes_campos.items():
            campo = campos[nombre]
            campo.error_messages.update(mensajes)
            for validador in campo.validators:
                if isinstance(validador, MaxLengthValidator) and "max_length" in mensajes:
                    validador.message = mensajes["max_length"]
                elif isinstance(validador, MinLengthValidator) and "min_length" in mensajes:
                    validador.message = mensajes["min_length"]
                elif isinstance(validador, EmailValidator) and "invalid" in mensajes:
                    validador.message = mensajes["invalid"]
        return campos

    def to_internal_value(self, data):
        request = self.context.get("request")
        if request and isinstance(data, Mapping):
            escribibles = {campo.field_name for campo in self._writable_fields}
            extras = set(data) - escribibles - {"csrfmiddlewaretoken"}
            if extras:
                try:
                    super().to_internal_value(data)
                except serializers.ValidationError as error:
                    errores = dict(error.detail)
                else:
                    errores = {}
                errores.update({
                    nombre: ["Campo no admitido por este endpoint."] for nombre in sorted(extras)
                })
                raise serializers.ValidationError(errores)
        return super().to_internal_value(data)


def validar_nombre_persona(valor):
    # La regla se comparte entre el estudiante y los integrantes de la comisión.
    signos = {" ", "-", "'", "’", "."}
    if not any(letra.isalpha() for letra in valor) or any(
        not (letra.isalpha() or letra in signos) for letra in valor
    ):
        raise serializers.ValidationError(
            "El nombre solo puede contener letras, espacios, guiones, apóstrofos y puntos."
        )
    return valor


def mensajes_texto(etiqueta, maximo=None):
    mensajes = {
        "required": f"Indique {etiqueta}.",
        "null": f"Indique {etiqueta}; no use null.",
        "blank": f"Indique {etiqueta}; no puede quedar vacío.",
    }
    if maximo is not None:
        mensajes["max_length"] = f"{etiqueta.capitalize()} no puede superar {maximo} caracteres."
    return mensajes


class CuentaSerializer(CamposJsonEsperadosMixin, serializers.ModelSerializer):
    mensajes_campos = {
        "email": {**mensajes_texto("un correo electrónico", 254), "invalid": FORMATO_EMAIL},
        "password": mensajes_texto("una contraseña"),
        "nombre": mensajes_texto("el nombre de la persona", 180),
        "rol": {
            "invalid_choice": FORMATO_ROL,
            "null": FORMATO_ROL,
            "required": "Indique un rol: administrador, coordinador o estudiante.",
        },
        "activo": {"invalid": FORMATO_BOOLEANO, "null": FORMATO_BOOLEANO},
    }
    email = serializers.EmailField(source="usuario.email", max_length=254)
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    expediente = serializers.PrimaryKeyRelatedField(
        queryset=Expediente.objects.all(), required=False, allow_null=True,
        error_messages={
            "does_not_exist": "No existe un expediente con el ID {pk_value}.",
            "incorrect_type": "Indique un ID de expediente entero.",
        },
    )

    class Meta:
        model = PerfilUsuario
        fields = ["id", "email", "password", "nombre", "rol", "activo", "expediente"]

    def validate_email(self, email):
        email = email.strip().lower()
        usuarios = get_user_model().objects.filter(email__iexact=email)
        nombres_usuario = get_user_model().objects.filter(username__iexact=email)
        if self.instance:
            usuarios = usuarios.exclude(pk=self.instance.usuario_id)
            nombres_usuario = nombres_usuario.exclude(pk=self.instance.usuario_id)
        if usuarios.exists() or nombres_usuario.exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo.")
        return email

    def validate_nombre(self, valor):
        return validar_nombre_persona(valor)

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Indique una contraseña inicial."})
        if attrs.get("password"):
            try:
                validate_password(attrs["password"])
            except DjangoValidationError as error:
                raise serializers.ValidationError({"password": error.messages}) from error
        rol = attrs.get("rol", getattr(self.instance, "rol", None))
        expediente = attrs.get("expediente", getattr(self.instance, "expediente", None))
        if rol != PerfilUsuario.Rol.ESTUDIANTE and expediente:
            raise serializers.ValidationError({"expediente": "Solo un estudiante puede vincular un expediente."})
        if expediente and PerfilUsuario.objects.filter(expediente=expediente).exclude(
            pk=self.instance.pk if self.instance else None
        ).exists():
            raise serializers.ValidationError({"expediente": "Este expediente ya está vinculado."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop("usuario")["email"]
        password = validated_data.pop("password")
        usuario = get_user_model().objects.create_user(username=email, email=email, password=password)
        perfil = usuario.perfil
        for campo, valor in validated_data.items():
            setattr(perfil, campo, valor)
        perfil.save()
        return perfil

    @transaction.atomic
    def update(self, instance, validated_data):
        email = validated_data.pop("usuario", {}).get("email")
        password = validated_data.pop("password", None)
        if email is not None:
            instance.usuario.email = email
            instance.usuario.username = email
        if password:
            instance.usuario.set_password(password)
        if email is not None or password:
            instance.usuario.save()
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save()
        return instance


class ImportarCuentasSerializer(CamposJsonEsperadosMixin, serializers.Serializer):
    mensajes_campos = {
        "archivo": {
            "required": "Adjunte el archivo CSV de cuentas.",
            "null": "Adjunte el archivo CSV de cuentas.",
            "invalid": "Adjunte un archivo CSV real; una URL o texto no es un archivo.",
            "empty": "El archivo CSV no puede estar vacío.",
        },
    }
    archivo = serializers.FileField()


class CambiarClaveSerializer(CamposJsonEsperadosMixin, serializers.Serializer):
    mensajes_campos = {
        "clave_actual": mensajes_texto("la contraseña actual"),
        "clave_nueva": mensajes_texto("la contraseña nueva"),
    }
    clave_actual = serializers.CharField(style={"input_type": "password"})
    clave_nueva = serializers.CharField(style={"input_type": "password"})

    def validate_clave_nueva(self, valor):
        try:
            validate_password(valor, user=self.context["request"].user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return valor


class ConfiguracionSistemaSerializer(CamposJsonEsperadosMixin, serializers.ModelSerializer):
    mensajes_campos = {
        "mantenimiento": {"invalid": FORMATO_BOOLEANO, "null": FORMATO_BOOLEANO},
        "mensaje": {"null": "El mensaje debe ser texto; use una cadena vacía para quitarlo.",
                    "max_length": "El mensaje no puede superar 300 caracteres."},
    }
    class Meta:
        model = ConfiguracionSistema
        fields = ["mantenimiento", "mensaje", "actualizado"]
        read_only_fields = ["actualizado"]


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="usuario.email", read_only=True)
    expediente_id = serializers.IntegerField(source="expediente.id", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = ["id", "email", "nombre", "rol", "activo", "expediente_id"]


class ExpedienteSerializer(CamposJsonEsperadosMixin, serializers.ModelSerializer):
    mensajes_campos = {
        "nombre": mensajes_texto("el nombre del estudiante", 180),
        "rut": mensajes_texto("el RUT del estudiante", 12),
        "anio_egreso": {"required": "Indique el año de egreso.",
                         "max_string_length": FORMATO_ANIO_EGRESO},
        "semestre_egreso": {"required": "Indique el semestre de egreso (1 o 2)."},
        "fecha_examen": {"required": "Indique la fecha del examen en formato AAAA-MM-DD.",
                         "datetime": FORMATO_FECHA_EXAMEN},
        "nota_examen": {
            "required": "Indique la nota del examen.",
            "max_digits": FORMATO_NOTA_EXAMEN,
            "max_whole_digits": FORMATO_NOTA_EXAMEN,
            "max_string_length": FORMATO_NOTA_EXAMEN,
        },
        "profesor_guia": mensajes_texto("el nombre del profesor guía", 180),
        "informante_1": mensajes_texto("el nombre del primer informante", 180),
        "informante_2": mensajes_texto("el nombre del segundo informante", 180),
        "informante_adicional": {
            "null": "El nombre del informante adicional debe ser texto; use una cadena vacía para quitarlo.",
            "max_length": "El nombre del informante adicional no puede superar 180 caracteres.",
        },
    }
    acta_id = serializers.IntegerField(source="acta.id", read_only=True)
    estudiante = PerfilUsuarioSerializer(source="perfil_estudiante", read_only=True)
    creado_por = serializers.CharField(source="creado_por.username", read_only=True)
    # La normalización se realiza antes de validar el formato y la unicidad del RUT.
    rut = serializers.CharField(max_length=12)
    anio_egreso = serializers.IntegerField(
        min_value=2020, max_value=2050,
        error_messages={
            "invalid": FORMATO_ANIO_EGRESO,
            "min_value": "El año de egreso debe estar entre 2020 y 2050.",
            "max_value": "El año de egreso debe estar entre 2020 y 2050.",
            "null": "Indique el año de egreso.",
        },
    )
    semestre_egreso = serializers.ChoiceField(
        choices=Expediente._meta.get_field("semestre_egreso").choices,
        error_messages={
            "invalid_choice": FORMATO_SEMESTRE_EGRESO,
            "null": "Indique el semestre de egreso (1 o 2).",
        },
    )
    fecha_examen = serializers.DateField(
        input_formats=["%Y-%m-%d"], format="%Y-%m-%d",
        error_messages={
            "invalid": FORMATO_FECHA_EXAMEN,
            "null": "Indique la fecha del examen en formato AAAA-MM-DD.",
        },
    )
    nota_examen = serializers.DecimalField(
        max_digits=2, decimal_places=1, min_value=Decimal("1.0"), max_value=Decimal("7.0"),
        error_messages={
            "invalid": FORMATO_NOTA_EXAMEN,
            "max_decimal_places": "Use como máximo un decimal en la nota del examen.",
            "min_value": "La nota del examen debe estar entre 1,0 y 7,0.",
            "max_value": "La nota del examen debe estar entre 1,0 y 7,0.",
            "null": "Indique la nota del examen.",
        },
    )
    profesor_guia = serializers.CharField(max_length=180, validators=[validar_nombre_persona])
    informante_1 = serializers.CharField(max_length=180, validators=[validar_nombre_persona])
    informante_2 = serializers.CharField(max_length=180, validators=[validar_nombre_persona])
    informante_adicional = serializers.CharField(
        max_length=180, required=False, allow_blank=True, validators=[validar_nombre_persona]
    )

    class Meta:
        model = Expediente
        fields = [
            "id", "nombre", "rut", "anio_egreso", "semestre_egreso", "fecha_examen",
            "nota_examen", "profesor_guia", "informante_1", "informante_2",
            "informante_adicional", "colegiatura", "fecha_colegiatura",
            "estudiante", "acta_id", "creado_por",  "fecha_creacion","fecha_actualizacion",
        ]
        read_only_fields = ["colegiatura", "fecha_colegiatura"]

    def validate_rut(self, valor):
        normalizado = normalizar_rut(valor)
        existentes = Expediente.objects.filter(rut=normalizado)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError("Ya existe un expediente con ese RUT.")
        return normalizado

    def validate_nombre(self, valor):
        return validar_nombre_persona(valor)

    def validate(self, attrs):
        # La comisión de examen no puede repetir a un docente en dos puestos.
        campos = ("profesor_guia", "informante_1", "informante_2", "informante_adicional")
        vistos = set()
        repetidos = {}
        for campo in campos:
            nombre = attrs.get(campo, getattr(self.instance, campo, ""))
            if not nombre.strip():
                continue
            normalizado = "".join(
                letra for letra in unicodedata.normalize("NFD", " ".join(nombre.split()).casefold())
                if not unicodedata.combining(letra)
            ).strip()
            if normalizado in vistos:
                repetidos[campo] = "Este docente ya figura en la comisión."
            vistos.add(normalizado)
        if repetidos:
            raise serializers.ValidationError(repetidos)
        return attrs
class ActaSerializer(CamposJsonEsperadosMixin, serializers.ModelSerializer):
    mensajes_campos = {
        "expediente": {
            "required": "Indique el ID del expediente al que pertenece el acta.",
            "null": "Indique el ID del expediente al que pertenece el acta.",
        },
        "archivo": {
            "null": "Adjunte un PDF o envíe archivo_base64 en JSON.",
            "empty": "El PDF del acta no puede estar vacío.",
            "max_length": "El nombre del PDF es demasiado largo.",
        },
        "archivo_base64": {
            "null": "Envíe el contenido Base64 del PDF como texto.",
            "blank": "Envíe el contenido Base64 del PDF; no puede estar vacío.",
        },
    }
    cargada_por = serializers.CharField(source="cargada_por.username", read_only=True)
    archivo = serializers.FileField(required=False, error_messages={
        "invalid": "Adjunte un archivo PDF real en el formulario; una URL o texto JSON no es un archivo.",
    })
    archivo_base64 = serializers.CharField(
        write_only=True, required=False,
        help_text="Para Raw data con application/json: contenido Base64 del PDF, sin prefijo data:.",
    )
    expediente = serializers.PrimaryKeyRelatedField(
        queryset=Expediente.objects.all(),
        error_messages={
            "does_not_exist": "No existe un expediente con el ID {pk_value}.",
            "incorrect_type": "Indique un ID de expediente entero.",
        },
    )

    class Meta:
        model = Acta
        fields = ["id", "expediente", "archivo", "archivo_base64", "nombre_original", "fecha_carga", "cargada_por"]
        read_only_fields = ["nombre_original", "fecha_carga", "cargada_por"]

    def validate_archivo(self, archivo):
        if not archivo.name.lower().endswith(".pdf") or archivo.size == 0 or archivo.size >= 10 * 1024 * 1024:
            raise serializers.ValidationError("El acta debe ser un PDF no vacío de menos de 10 MB.")
        cabecera = archivo.read(5)
        archivo.seek(0)
        if cabecera != b"%PDF-":
            raise serializers.ValidationError("El archivo no tiene una cabecera PDF válida.")
        return archivo

    def validate_expediente(self, expediente):
        existentes = Acta.objects.filter(expediente=expediente)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError("Este expediente ya tiene un acta; edite la existente.")
        return expediente

    def validate(self, attrs):
        codificado = attrs.pop("archivo_base64", None)
        if "archivo" in attrs and codificado is not None:
            raise serializers.ValidationError({
                "archivo_base64": "Envíe solo archivo o archivo_base64, no ambos."
            })
        if codificado is not None:
            limite = 10 * 1024 * 1024
            if len(codificado) > 4 * ((limite + 2) // 3):
                raise serializers.ValidationError({"archivo_base64": "El PDF debe ser menor de 10 MB."})
            try:
                contenido = base64.b64decode(codificado, validate=True)
            except (binascii.Error, ValueError) as error:
                raise serializers.ValidationError({
                    "archivo_base64": "Ingrese Base64 válido del PDF, sin prefijo data:."
                }) from error
            try:
                attrs["archivo"] = self.validate_archivo(ContentFile(contenido, name="acta.pdf"))
            except serializers.ValidationError as error:
                raise serializers.ValidationError({"archivo_base64": error.detail}) from error
        if self.instance is None and "archivo" not in attrs:
            raise serializers.ValidationError({
                "archivo": "Adjunte un PDF o envíe archivo_base64 en JSON."
            })
        return attrs

    def create(self, validated_data):
        archivo = validated_data["archivo"]
        return Acta.objects.create(**validated_data, nombre_original=archivo.name)

    def update(self, instance, validated_data):
        if "archivo" in validated_data:
            instance.nombre_original = validated_data["archivo"].name
        return super().update(instance, validated_data)


class DocumentoExpedienteSerializer(serializers.ModelSerializer):
    cargado_por = serializers.CharField(source="cargado_por.username", read_only=True)

    class Meta:
        model = DocumentoExpediente
        fields = ["id", "expediente", "archivo", "nombre_original", "tipo", "tamano", "fecha_carga", "cargado_por"]
        read_only_fields = fields


class CargaDocumentosSerializer(serializers.Serializer):
    archivos = serializers.ListField(
        child=serializers.FileField(), min_length=1, max_length=20,
        style={"template": "gestion/multiple_file_input.html"},
    )
    expedientes = serializers.CharField(
        help_text="IDs de destino separados por comas, uno por archivo y en el mismo orden."
    )


class DocumentoBase64Serializer(CamposJsonEsperadosMixin, serializers.Serializer):
    mensajes_campos = {
        "nombre": mensajes_texto("el nombre del archivo", 255),
        "contenido_base64": mensajes_texto("el contenido Base64 del archivo"),
        "expediente": {
            "required": "Indique el ID del expediente de este archivo.",
            "null": "Indique el ID del expediente de este archivo.",
        },
    }
    expediente = serializers.PrimaryKeyRelatedField(
        queryset=Expediente.objects.all(),
        error_messages={
            "does_not_exist": "No existe un expediente con el ID {pk_value}.",
            "incorrect_type": "Indique un ID de expediente entero.",
        },
    )
    nombre = serializers.CharField(max_length=255)
    contenido_base64 = serializers.CharField()

    def validate_nombre(self, valor):
        if "/" in valor or "\\" in valor:
            raise serializers.ValidationError("Indique solo el nombre del archivo, sin carpetas.")
        if Path(valor).suffix.lower() not in EXTENSIONES:
            raise serializers.ValidationError("Formato no admitido. Use PDF, DOCX, XLSX, PNG, JPG, TXT o CSV.")
        return valor

    def validate(self, attrs):
        codificado = attrs.pop("contenido_base64")
        if len(codificado) > 4 * ((MAX_BYTES_ARCHIVO + 2) // 3):
            raise serializers.ValidationError({
                "contenido_base64": "Cada archivo debe ser menor de 10 MB."
            })
        try:
            contenido = base64.b64decode(codificado, validate=True)
        except (binascii.Error, ValueError) as error:
            raise serializers.ValidationError({
                "contenido_base64": "Ingrese Base64 válido, sin prefijo data:."
            }) from error
        archivo = SimpleUploadedFile(attrs.pop("nombre"), contenido)
        try:
            validar_documento(archivo)
        except serializers.ValidationError as error:
            raise serializers.ValidationError({
                "contenido_base64": error.detail["archivos"]
            }) from error
        attrs["archivo"] = archivo
        return attrs


class CargaMasivaJsonSerializer(CamposJsonEsperadosMixin, serializers.Serializer):
    mensajes_campos = {
        "archivos": {
            "required": "Envíe al menos un archivo.",
            "null": "Envíe una lista de archivos.",
            "not_a_list": "archivos debe ser una lista de objetos con expediente, nombre y contenido_base64.",
            "min_length": "Envíe al menos un archivo.",
            "max_length": f"Envíe como máximo {MAX_ARCHIVOS} archivos.",
        },
    }
    archivos = serializers.ListField(
        child=DocumentoBase64Serializer(), min_length=1, max_length=MAX_ARCHIVOS,
    )


class CargaDocumentosExpedienteSerializer(serializers.Serializer):
    archivos = serializers.ListField(
        child=serializers.FileField(), min_length=1, max_length=20,
        style={"template": "gestion/multiple_file_input.html"},
    )


class CambioColegiaturaSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = CambioColegiatura
        fields = ["id", "estado_anterior", "estado_nuevo", "fecha", "usuario", "observacion"]


class NuevoEstadoColegiaturaSerializer(CamposJsonEsperadosMixin, serializers.Serializer):
    mensajes_campos = {
        "estado_nuevo": {
            "required": "Indique el nuevo estado de colegiatura.",
            "null": FORMATO_ESTADO_COLEGIATURA,
            "invalid_choice": FORMATO_ESTADO_COLEGIATURA,
        },
        "observacion": {
            "null": "La observación debe ser texto; use una cadena vacía si no hay observación.",
            "max_length": "La observación no puede superar 1000 caracteres.",
        },
    }
    estado_nuevo = serializers.ChoiceField(choices=Expediente.EstadoColegiatura.choices)
    observacion = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = RegistroAuditoria
        fields = ["id", "usuario", "accion", "detalles", "fecha"]
