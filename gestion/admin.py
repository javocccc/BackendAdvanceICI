from django.contrib import admin

from .models import Expediente, PerfilUsuario


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ("rut", "nombre", "fecha_examen", "colegiatura")
    search_fields = ("rut", "nombre")
    list_filter = ("colegiatura", "anio_egreso")


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "usuario", "rol", "activo", "expediente")
    list_filter = ("rol", "activo")
