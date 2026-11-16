import base64
import json
from datetime import date
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Acta, Expediente


class ValidadoresAPITests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            "admin-validacion", "admin-validacion@example.com", "ClaveSegura123!"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.expediente_valido = {
            "nombre": "Valentina Soto", "rut": "22.222.222-2",
            "anio_egreso": 2026, "semestre_egreso": 1,
            "fecha_examen": "2026-11-10", "nota_examen": "6.3",
            "profesor_guia": "María Fuentes", "informante_1": "Carlos Vega",
            "informante_2": "Paula Torres",
        }

    def test_rechaza_numeros_fuera_de_rango_y_fechas_invalidas(self):
        casos = [
            ("anio_egreso", -1), ("anio_egreso", 2019), ("anio_egreso", 2051),
            ("semestre_egreso", 0), ("semestre_egreso", 3),
            ("nota_examen", "-1.0"), ("nota_examen", "0.0"),
            ("nota_examen", "7.1"), ("nota_examen", "6.33"),
            ("fecha_examen", "2026-02-30"), ("fecha_examen", "10/11/2026"),
        ]
        for campo, valor in casos:
            with self.subTest(campo=campo, valor=valor):
                datos = {**self.expediente_valido, campo: valor}
                respuesta = self.client.post("/api/expedientes/", datos, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
        self.assertEqual(Expediente.objects.count(), 0)

    def test_raw_json_explica_sintaxis_y_valores_invalidos_de_expediente(self):
        casos = (
            ("anio_egreso", "hola", "año de egreso entero"),
            ("semestre_egreso", "hola", "debe ser 1 o 2"),
            ("fecha_examen", "hola", "formato AAAA-MM-DD"),
            ("nota_examen", "hola", "nota numérica"),
            ("fecha_examen", None, "Indique la fecha"),
        )
        for campo, valor, mensaje in casos:
            with self.subTest(campo=campo, valor=valor):
                respuesta = self.client.post(
                    "/api/expedientes/", {**self.expediente_valido, campo: valor}, format="json"
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(mensaje, str(respuesta.data[campo]))

        for campo, _, mensaje in casos[:4]:
            with self.subTest(json_sin_comillas=campo):
                valor_original = json.dumps(self.expediente_valido[campo])
                cuerpo = json.dumps(self.expediente_valido).replace(
                    f'"{campo}": {valor_original}', f'"{campo}": hola'
                )
                respuesta = self.client.generic(
                    "POST", "/api/expedientes/", cuerpo, content_type="application/json"
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                detalle = str(respuesta.data["detail"])
                self.assertIn("JSON mal formado", detalle)
                self.assertIn(campo, detalle)
                self.assertIn(mensaje, detalle)
                self.assertNotIn("línea", detalle)
                self.assertNotIn("columna", detalle)

        respuesta = self.client.generic(
            "POST", "/api/expedientes/", '{"anio_egreso": 2026,}',
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("Respete el formato JSON", str(respuesta.data["detail"]))
        self.assertNotIn("línea", str(respuesta.data["detail"]))
        self.assertEqual(Expediente.objects.count(), 0)

    def test_rechaza_campos_obligatorios_y_docentes_repetidos(self):
        for campo in ("nota_examen", "profesor_guia", "informante_1", "informante_2"):
            with self.subTest(campo=campo):
                datos = self.expediente_valido.copy()
                datos.pop(campo)
                respuesta = self.client.post("/api/expedientes/", datos, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
        repetidos = {**self.expediente_valido, "informante_1": "Maria   Fuentes"}
        respuesta = self.client.post("/api/expedientes/", repetidos, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("informante_1", respuesta.data)

    def test_nombre_expediente_no_admite_cifras(self):
        for nombre in ("2", "Camila2", "123456"):
            with self.subTest(nombre=nombre):
                respuesta = self.client.post(
                    "/api/expedientes/", {**self.expediente_valido, "nombre": nombre}, format="json"
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn("nombre", respuesta.data)
        valido = self.client.post(
            "/api/expedientes/", {**self.expediente_valido, "nombre": "María-José O'Connor"}, format="json"
        )
        self.assertEqual(valido.status_code, 201, valido.data)
        edicion = self.client.patch(
            f"/api/expedientes/{valido.data['id']}/", {"nombre": "2"}, format="json"
        )
        self.assertEqual(edicion.status_code, 400, edicion.data)
        self.assertEqual(Expediente.objects.get(pk=valido.data["id"]).nombre, "María-José O'Connor")

    def test_docentes_rechazan_cifras_al_crear_y_editar(self):
        campos = ("profesor_guia", "informante_1", "informante_2", "informante_adicional")
        for campo in campos:
            for nombre in ("2", "Ana2"):
                with self.subTest(campo=campo, nombre=nombre):
                    respuesta = self.client.post(
                        "/api/expedientes/", {**self.expediente_valido, campo: nombre}, format="json"
                    )
                    self.assertEqual(respuesta.status_code, 400, respuesta.data)
                    self.assertIn(campo, respuesta.data)
        formulario = self.client.post(
            "/api/expedientes/", {**self.expediente_valido, "profesor_guia": "2"}, format="multipart"
        )
        self.assertEqual(formulario.status_code, 400, formulario.data)
        self.assertIn("profesor_guia", formulario.data)

        creado = self.client.post(
            "/api/expedientes/",
            {**self.expediente_valido, "informante_adicional": "Ana-María O'Connor"},
            format="json",
        )
        self.assertEqual(creado.status_code, 201, creado.data)
        expediente = Expediente.objects.get(pk=creado.data["id"])
        for campo in campos:
            with self.subTest(edicion=campo):
                anterior = getattr(expediente, campo)
                respuesta = self.client.patch(
                    f"/api/expedientes/{expediente.pk}/", {campo: "2"}, format="json"
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
                expediente.refresh_from_db()
                self.assertEqual(getattr(expediente, campo), anterior)
        quitar_opcional = self.client.patch(
            f"/api/expedientes/{expediente.pk}/", {"informante_adicional": ""}, format="json"
        )
        self.assertEqual(quitar_opcional.status_code, 200, quitar_opcional.data)

    def test_raw_json_rechaza_claves_ajenas_y_campos_de_solo_lectura(self):
        for campo, valor in (("anioEgreso", 2026), ("colegiatura", "al-dia"), ("id", 99)):
            with self.subTest(campo=campo):
                datos = {**self.expediente_valido, campo: valor}
                respuesta = self.client.post("/api/expedientes/", datos, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)

    def test_acepta_valores_validos_y_rechaza_rut_duplicado(self):
        datos = {**self.expediente_valido, "rut": "222222222"}
        creado = self.client.post("/api/expedientes/", datos, format="json")
        self.assertEqual(creado.status_code, 201, creado.data)
        self.assertEqual(creado.data["rut"], "22.222.222-2")
        duplicado = self.client.post("/api/expedientes/", self.expediente_valido, format="json")
        self.assertEqual(duplicado.status_code, 400, duplicado.data)
        self.assertIn("rut", duplicado.data)
        basura = self.client.post(
            "/api/expedientes/", {**self.expediente_valido, "rut": "abc22.222.222-2"}, format="json"
        )
        self.assertEqual(basura.status_code, 400, basura.data)
        formato = self.client.post(
            "/api/expedientes/", {**self.expediente_valido, "rut": "22-222-222-2"}, format="json"
        )
        self.assertEqual(formato.status_code, 400, formato.data)

    def test_cuenta_rechaza_email_rol_y_clave_invalidos(self):
        base = {"email": "nuevo@example.com", "password": "ClaveSegura123!",
                "nombre": "Alumno Nuevo", "rol": "estudiante", "activo": True}
        casos = [("email", "sin-correo"), ("rol", "profesor"), ("password", "123456")]
        for campo, valor in casos:
            with self.subTest(campo=campo):
                respuesta = self.client.post("/api/cuentas/", {**base, campo: valor}, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
        respuesta = self.client.post("/api/cuentas/", {**base, "rolNuevo": "administrador"}, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("rolNuevo", respuesta.data)

    def test_cuenta_raw_data_muestra_mensajes_propios_por_campo(self):
        base = {"email": "persona@example.com", "password": "ClaveSegura123!",
                "nombre": "Persona Nueva", "rol": "estudiante", "activo": True}
        casos = (
            ("rol", "cualquier-rol", "administrador, coordinador o estudiante"),
            ("rol", 42, "administrador, coordinador o estudiante"),
            ("rol", None, "administrador, coordinador o estudiante"),
            ("activo", "hola", "true o false"),
            ("email", "sin-arroba", "correo electrónico válido"),
            ("nombre", "", "no puede quedar vacío"),
            ("password", "123456", "contraseña"),
        )
        for campo, valor, mensaje in casos:
            with self.subTest(campo=campo, valor=valor):
                respuesta = self.client.post(
                    "/api/cuentas/", {**base, campo: valor}, format="json"
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
                self.assertIn(mensaje.lower(), str(respuesta.data[campo]).lower())

        for campo in ("rol", "activo", "email"):
            respuesta = self.client.generic(
                "POST", "/api/cuentas/", f'{{"{campo}": hola}}',
                content_type="application/json",
            )
            self.assertEqual(respuesta.status_code, 400, respuesta.data)
            self.assertIn(campo, str(respuesta.data["detail"]))
        self.assertFalse(get_user_model().objects.filter(email=base["email"]).exists())

    def test_otros_formularios_raw_data_muestran_campo_y_formato(self):
        expediente = Expediente.objects.create(
            nombre="Alumno Prueba", rut="12.345.678-5", anio_egreso=2026,
            semestre_egreso=1, fecha_examen=date(2026, 11, 10), creado_por=self.admin,
        )
        casos = (
            (f"/api/expedientes/{expediente.pk}/colegiatura/", "estado_nuevo",
             "inventado", "al-dia, no-al-dia o sin-informar"),
            ("/api/estado/", "mantenimiento", "hola", "true o false"),
        )
        for url, campo, valor, mensaje in casos:
            with self.subTest(url=url, campo=campo):
                metodo = self.client.put if campo == "mantenimiento" else self.client.post
                respuesta = metodo(url, {campo: valor}, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(mensaje, str(respuesta.data[campo]))
                bruto = self.client.generic(
                    "PUT" if campo == "mantenimiento" else "POST",
                    url, f'{{"{campo}": hola}}', content_type="application/json",
                )
                self.assertEqual(bruto.status_code, 400, bruto.data)
                self.assertIn(campo, str(bruto.data["detail"]))

        respuesta = self.client.post("/api/cambiar-clave/", {
            "clave_actual": "ClaveSegura123!", "clave_nueva": "123456",
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("clave_nueva", respuesta.data)

    def test_expediente_raw_data_rechaza_textos_y_nulos_con_detalle(self):
        casos = (
            ("nombre", "", "no puede quedar vacío"),
            ("rut", None, "no use null"),
            ("profesor_guia", None, "no use null"),
            ("informante_adicional", None, "debe ser texto"),
            ("nota_examen", "123", "nota numérica"),
        )
        for campo, valor, mensaje in casos:
            with self.subTest(campo=campo):
                respuesta = self.client.post(
                    "/api/expedientes/", {**self.expediente_valido, campo: valor}, format="json"
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(mensaje, str(respuesta.data[campo]))
        respuesta = self.client.post("/api/expedientes/", {
            **self.expediente_valido, "anio_egreso": "hola", "id": 999,
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("anio_egreso", respuesta.data)
        self.assertIn("id", respuesta.data)

    def test_limites_y_reglas_cruzadas_indican_campo(self):
        cuenta = {"email": "persona@example.com", "password": "ClaveSegura123!",
                  "nombre": "Persona Nueva", "rol": "estudiante"}
        casos = (
            ("/api/cuentas/", {**cuenta, "nombre": "A" * 181},
             "nombre", "180 caracteres"),
            ("/api/cuentas/", {**cuenta, "email": "a" * 250 + "@b.cl"},
             "email", "254 caracteres"),
            ("/api/expedientes/", {**self.expediente_valido, "profesor_guia": "A" * 181},
             "profesor_guia", "180 caracteres"),
            ("/api/actas/", {"expediente": 1, "archivo_base64": ""},
             "archivo_base64", "no puede estar vacío"),
        )
        for url, datos, campo, mensaje in casos:
            with self.subTest(url=url, campo=campo):
                respuesta = self.client.post(url, datos, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(mensaje, str(respuesta.data[campo]))

        respuesta = self.client.put("/api/estado/", {
            "mantenimiento": False, "mensaje": "A" * 301,
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("300 caracteres", str(respuesta.data["mensaje"]))

        expediente = Expediente.objects.create(
            nombre="Alumno Prueba", rut="12.345.678-5", anio_egreso=2026,
            semestre_egreso=1, fecha_examen=date(2026, 11, 10), creado_por=self.admin,
        )
        url = f"/api/expedientes/{expediente.pk}/colegiatura/"
        respuesta = self.client.post(url, {
            "estado_nuevo": "sin-informar",
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("estado_nuevo", respuesta.data)
        respuesta = self.client.post(url, {
            "estado_nuevo": "al-dia", "observacion": "A" * 1001,
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("1000 caracteres", str(respuesta.data["observacion"]))

    def test_importacion_y_documentos_explican_formato_de_archivo(self):
        incorrecto = SimpleUploadedFile("cuentas.txt", b"nombre,email,rut\n")
        respuesta = self.client.post("/api/cuentas/importar/", {
            "archivo": incorrecto,
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("extensión .csv", str(respuesta.data["archivo"]))

        for url in ("/api/cuentas/importar/", "/api/documentos/carga-masiva/"):
            with self.subTest(url=url):
                respuesta = self.client.generic(
                    "POST", url, b'{"archivo": "texto"}',
                    content_type="multipart/form-data",
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn("Use el formulario para adjuntar archivos", str(respuesta.data["detail"]))

    def test_administrador_no_puede_quitarse_su_acceso(self):
        url = f"/api/cuentas/{self.admin.perfil.pk}/"
        for campo, valor in (("rol", "estudiante"), ("activo", False)):
            with self.subTest(campo=campo):
                respuesta = self.client.patch(url, {campo: valor}, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
        self.admin.perfil.refresh_from_db()
        self.assertEqual(self.admin.perfil.rol, "administrador")
        self.assertTrue(self.admin.perfil.activo)

    def test_acta_no_se_mueve_a_expediente_con_acta_existente(self):
        primero = Expediente.objects.create(
            nombre="Primero", rut="12.345.678-5", anio_egreso=2025,
            semestre_egreso=1, fecha_examen=date(2026, 11, 10), creado_por=self.admin,
        )
        segundo = Expediente.objects.create(
            nombre="Segundo", rut="11.111.111-1", anio_egreso=2025,
            semestre_egreso=1, fecha_examen=date(2026, 11, 10), creado_por=self.admin,
        )
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        with override_settings(MEDIA_ROOT=carpeta):
            ids = []
            for expediente in (primero, segundo):
                archivo = SimpleUploadedFile("acta.pdf", b"%PDF-1.4\ncontenido", content_type="application/pdf")
                respuesta = self.client.post("/api/actas/", {
                    "expediente": expediente.pk, "archivo": archivo,
                }, format="multipart")
                self.assertEqual(respuesta.status_code, 201, respuesta.data)
                ids.append(respuesta.data["id"])
            cambio = self.client.patch(f"/api/actas/{ids[0]}/", {"expediente": segundo.pk}, format="multipart")
            self.assertEqual(cambio.status_code, 400, cambio.data)
            self.assertIn("expediente", cambio.data)

    def test_importacion_csv_informa_fila_con_columnas_extra(self):
        archivo = SimpleUploadedFile(
            "alumnos.csv", b"nombre,email,rut\nAlumno,alumno@example.com,,extra\n", content_type="text/csv"
        )
        respuesta = self.client.post("/api/cuentas/importar/", {"archivo": archivo}, format="multipart")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertIn("error", respuesta.data["resultados"][0])

    def test_acta_raw_data_informa_id_inexistente_y_campos_ajenos(self):
        archivo = lambda: SimpleUploadedFile("acta.pdf", b"%PDF-1.4\ncontenido")
        respuesta = self.client.post("/api/actas/", {
            "expediente": 10, "archivo": archivo(),
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("No existe un expediente con el ID 10", str(respuesta.data["expediente"]))
        self.assertEqual(Acta.objects.count(), 0)

        respuesta = self.client.post("/api/actas/", {
            "expediente": "abc", "archivo": archivo(),
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("ID de expediente entero", str(respuesta.data["expediente"]))

        respuesta = self.client.post("/api/actas/", {
            "expediente": 10, "archivo": archivo(), "nombre_original": "falso.pdf",
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("nombre_original", respuesta.data)
        self.assertEqual(Acta.objects.count(), 0)

    def test_acta_raw_data_explica_multipart_sin_boundary(self):
        respuesta = self.client.generic(
            "POST", "/api/actas/", b'{"expediente": 10}',
            content_type="multipart/form-data",
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("adjunte un PDF", str(respuesta.data["detail"]))
        self.assertEqual(Acta.objects.count(), 0)

    def test_acta_raw_data_muestra_json_y_plantilla(self):
        respuesta = self.client.get("/api/actas/", HTTP_ACCEPT="text/html")
        self.assertEqual(respuesta.status_code, 200, respuesta.content[:500])
        contenido = respuesta.content.decode()
        self.assertIn('value="application/json" selected', contenido)
        self.assertIn('&quot;archivo_base64&quot;: &quot;&quot;', contenido)

    def test_acta_json_informa_url_y_acta_ya_existente(self):
        expediente = Expediente.objects.create(
            nombre="Alumno Prueba", rut="12.345.678-5", anio_egreso=2026,
            semestre_egreso=1, fecha_examen=date(2026, 11, 10), creado_por=self.admin,
        )
        Acta.objects.create(
            expediente=expediente, archivo="actas/1/existente.pdf",
            nombre_original="existente.pdf", cargada_por=self.admin,
        )
        respuesta = self.client.post("/api/actas/", {
            "expediente": expediente.pk, "archivo": "http://127.0.0.1:8000/media/actas/1/existente.pdf",
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("una URL o texto JSON no es un archivo", str(respuesta.data["archivo"]))
        self.assertIn("ya tiene un acta", str(respuesta.data["expediente"]))
        self.assertEqual(Acta.objects.count(), 1)

    def test_acta_raw_json_base64_carga_pdf_y_valida_errores(self):
        expediente = Expediente.objects.create(
            nombre="Alumno Prueba", rut="12.345.678-5", anio_egreso=2026,
            semestre_egreso=1, fecha_examen=date(2026, 11, 10), creado_por=self.admin,
        )
        url = "/api/actas/"
        for contenido, mensaje in (("no-es-base64!", "Base64 válido"),
                                   (base64.b64encode(b"no es pdf").decode(), "cabecera PDF")):
            with self.subTest(contenido=contenido):
                respuesta = self.client.post(url, {
                    "expediente": expediente.pk, "archivo_base64": contenido,
                }, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(mensaje, str(respuesta.data["archivo_base64"]))
        self.assertEqual(Acta.objects.count(), 0)

        pdf = b"%PDF-1.4\ncontenido"
        codificado = base64.b64encode(pdf).decode("ascii")
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        with override_settings(MEDIA_ROOT=carpeta):
            respuesta = self.client.post(url, {
                "expediente": expediente.pk, "archivo_base64": codificado,
            }, format="json")
            self.assertEqual(respuesta.status_code, 201, respuesta.data)
            self.assertNotIn("archivo_base64", respuesta.data)
            acta = Acta.objects.get(pk=respuesta.data["id"])
            with acta.archivo.open("rb") as guardado:
                self.assertEqual(guardado.read(), pdf)
            repetido = self.client.post(url, {
                "expediente": expediente.pk, "archivo_base64": codificado,
            }, format="json")
            self.assertEqual(repetido.status_code, 400, repetido.data)
            self.assertIn("ya tiene un acta", str(repetido.data["expediente"]))
            self.assertEqual(Acta.objects.count(), 1)
            nuevo_pdf = b"%PDF-1.4\ncontenido actualizado"
            reemplazo = self.client.patch(f"/api/actas/{acta.pk}/", {
                "archivo_base64": base64.b64encode(nuevo_pdf).decode("ascii"),
            }, format="json")
            self.assertEqual(reemplazo.status_code, 200, reemplazo.data)
            acta.refresh_from_db()
            with acta.archivo.open("rb") as guardado:
                self.assertEqual(guardado.read(), nuevo_pdf)

    def test_cuenta_raw_data_informa_id_inexistente_y_nombre_invalido(self):
        base = {"email": "alumno@example.com", "password": "ClaveSegura123!",
                "nombre": "Alumno Nuevo", "rol": "estudiante"}
        respuesta = self.client.post("/api/cuentas/", {
            **base, "expediente": 10,
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("No existe un expediente con el ID 10", str(respuesta.data["expediente"]))
        respuesta = self.client.post("/api/cuentas/", {
            **base, "nombre": "Alumno 123",
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("nombre", respuesta.data)
        self.assertFalse(get_user_model().objects.filter(email=base["email"]).exists())
