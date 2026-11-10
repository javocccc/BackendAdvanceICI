from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Expediente, PerfilUsuario


class ExpedienteAPITests(TestCase):
    def setUp(self):
        usuarios = get_user_model()
        self.admin = usuarios.objects.create_superuser("admin", "admin@example.com", "ClaveSegura123!")
        self.coordinador = usuarios.objects.create_user("coord", "coord@example.com", "ClaveSegura123!")
        self.coordinador.perfil.rol = PerfilUsuario.Rol.COORDINADOR
        self.coordinador.perfil.save()
        self.estudiante = usuarios.objects.create_user("alumno", "alumno@example.com", "ClaveSegura123!")
        self.expediente = Expediente.objects.create(
            nombre="Camila Rojas", rut="12.345.678-5", anio_egreso=2025,
            semestre_egreso=2, fecha_examen=date(2026, 10, 15), creado_por=self.admin,
        )
        self.otro = Expediente.objects.create(
            nombre="Diego Pérez", rut="11.111.111-1", anio_egreso=2024,
            semestre_egreso=1, fecha_examen=date(2026, 9, 10), creado_por=self.admin,
        )
        self.estudiante.perfil.expediente = self.expediente
        self.estudiante.perfil.save()
        self.client = APIClient()

    def test_anonimo_no_puede_leer(self):
        self.assertEqual(self.client.get("/api/expedientes/").status_code, 403)

    def test_estudiante_solo_lee_su_expediente(self):
        self.client.force_authenticate(self.estudiante)
        respuesta = self.client.get("/api/expedientes/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["count"], 1)
        self.assertEqual(self.client.get(f"/api/expedientes/{self.otro.pk}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/expedientes/{self.expediente.pk}/").status_code, 403)

    def test_coordinador_hace_crud_y_busca(self):
        self.client.force_authenticate(self.coordinador)
        nuevo = {
            "nombre": "Valentina Soto", "rut": "22.222.222-2", "anio_egreso": 2026,
            "semestre_egreso": 1, "fecha_examen": "2026-11-04",
        }
        creado = self.client.post("/api/expedientes/", nuevo)
        self.assertEqual(creado.status_code, 201, creado.data)
        pk = creado.data["id"]
        self.assertEqual(creado.data["creado_por"], "coord")
        self.assertEqual(self.client.get("/api/expedientes/?search=Valentina").data["count"], 1)
        self.assertEqual(self.client.get("/api/expedientes/?anio_egreso=2026").data["count"], 1)
        self.assertEqual(self.client.patch(f"/api/expedientes/{pk}/", {"nombre": "Valentina Soto A."}).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/expedientes/{pk}/").status_code, 204)

    def test_rut_invalido_y_duplicado(self):
        self.client.force_authenticate(self.admin)
        datos = {
            "nombre": "Otro", "rut": "12.345.678-0", "anio_egreso": 2025,
            "semestre_egreso": 1, "fecha_examen": "2026-11-04",
        }
        self.assertEqual(self.client.post("/api/expedientes/", datos).status_code, 400)
        datos["rut"] = "123456785"
        self.assertEqual(self.client.post("/api/expedientes/", datos).status_code, 400)

    def test_paginacion(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.get("/api/expedientes/?page=1")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("results", respuesta.data)
