from rest_framework import serializers

from .models import Acta, CambioColegiatura, Expediente, PerfilUsuario, RegistroAuditoria
from .rut import normalizar_rut


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="usuario.email", read_only=True)
    expediente_id = serializers.IntegerField(source="expediente.id", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = ["id", "email", "nombre", "rol", "activo", "expediente_id"]


class ExpedienteSerializer(serializers.ModelSerializer):
    acta_id = serializers.IntegerField(source="acta.id", read_only=True)
    estudiante = PerfilUsuarioSerializer(source="perfil_estudiante", read_only=True)
    creado_por = serializers.CharField(source="creado_por.username", read_only=True)

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
        return normalizar_rut(valor)

    def validate(self, attrs):
        # La comisión de examen no puede repetir a un docente en dos puestos.
        campos = ("profesor_guia", "informante_1", "informante_2", "informante_adicional")
        nombres = [attrs.get(campo, getattr(self.instance, campo, "")) for campo in campos]
        presentes = [nombre.strip().casefold() for nombre in nombres if nombre.strip()]
        if len(presentes) != len(set(presentes)):
            raise serializers.ValidationError("Un docente aparece más de una vez en la comisión.")
        return attrs
class ActaSerializer(serializers.ModelSerializer):
    cargada_por = serializers.CharField(source="cargada_por.username", read_only=True)

    class Meta:
        model = Acta
        fields = ["id", "expediente", "archivo", "nombre_original", "fecha_carga", "cargada_por"]
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
        if self.instance is None and Acta.objects.filter(expediente=expediente).exists():
            raise serializers.ValidationError("Este expediente ya tiene un acta; edite la existente.")
        return expediente

    def create(self, validated_data):
        archivo = validated_data["archivo"]
        return Acta.objects.create(**validated_data, nombre_original=archivo.name)

    def update(self, instance, validated_data):
        if "archivo" in validated_data:
            instance.nombre_original = validated_data["archivo"].name
        return super().update(instance, validated_data)
