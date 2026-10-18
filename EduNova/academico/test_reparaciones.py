from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch
from datetime import timedelta

from django.apps import apps
from django.contrib.messages import get_messages
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Usuario
from .models import Carrera, Asignatura, Curso, Estudiante, ObservacionComportamiento, SesionClase, MarcaAsistencia, AvisoAsistencia, RegistroAsistencia, Asistencia


class ReparacionesFlujosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carrera = Carrera.objects.create(nombre='Carrera pruebas de flujos', escuela='Pruebas')
        cls.otra = Carrera.objects.create(nombre='Otra carrera de flujos', escuela='Pruebas')
        cls.materia = Asignatura.objects.create(codigo='MAT-FLUJOS', nombre='Matemática')
        cls.materia.carreras.add(cls.carrera)
        cls.ajena = Asignatura.objects.create(codigo='HIS-FLUJOS', nombre='Historia')
        cls.ajena.carreras.add(cls.otra)
        cls.profesor = Usuario.objects.create_user(rut='70000000-1', rol='docente')
        cls.director = Usuario.objects.create_user(rut='70000000-2', rol='administrativo', carrera_dirigida=cls.carrera)
        cls.admin = Usuario.objects.create_superuser(rut='70000000-3')
        cls.seccion = Curso.objects.create(asignatura_catalogo=cls.materia, turno=True, docente_jefe=cls.profesor)
        cls.seccion.docentes.add(cls.profesor)
        cls.alumno = Usuario.objects.create_user(rut='70000000-4', first_name='Ana', apellidos='Pérez', rol='estudiante', curso=cls.seccion)
        cls.perfil = Estudiante.objects.get(usuario=cls.alumno)
        cls.perfil.carrera = cls.carrera
        cls.perfil.save()

    def test_opciones_filtran_carrera_y_previsualizan_siguiente_numero(self):
        self.client.force_login(self.director)
        url = reverse('academico:opciones_seccion')
        response = self.client.get(url, {'carrera':self.carrera.pk,'asignatura':self.materia.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['numero'], '001')
        self.assertEqual([a['id'] for a in response.json()['asignaturas']], [self.materia.pk])
        self.assertEqual(self.client.get(url, {'carrera':self.otra.pk}).status_code, 200)
        self.assertEqual(self.client.get(url, {'carrera':self.carrera.pk,'asignatura':self.ajena.pk}).status_code, 404)
        self.assertEqual(self.client.get(url, {'carrera':'incorrecto'}).status_code, 404)

    def test_crear_seccion_ignora_numero_enviado_y_guarda_docentes_y_turno(self):
        self.client.force_login(self.director)
        response = self.client.post(reverse('academico:crear_curso'), {'carrera':self.carrera.pk,'asignatura_catalogo':self.materia.pk,'turno':'false','docentes':[self.profesor.pk],'numero_previo':'888'})
        self.assertRedirects(response, reverse('academico:home_administrativo'))
        nueva = Curso.objects.exclude(pk=self.seccion.pk).get()
        self.assertEqual(nueva.seccion,'MAT-001-V')
        self.assertIs(nueva.turno,False)
        self.assertEqual(list(nueva.docentes.all()),[self.profesor])

    def test_carrera_y_asignatura_ajenas_no_se_pueden_crear(self):
        self.client.force_login(self.director)
        response = self.client.post(reverse('academico:crear_curso'), {'carrera':self.carrera.pk,'asignatura_catalogo':self.ajena.pk,'turno':'true','docentes':[self.profesor.pk]})
        self.assertEqual(response.status_code,200)
        self.assertIn('asignatura_catalogo',response.context['form'].errors)
        self.assertEqual(Curso.objects.count(),1)

    def test_numero_agotado_se_informa_en_formulario_y_previsualizacion(self):
        Curso.objects.bulk_create([Curso(asignatura='Matemática',seccion='MAT-999-D')])
        self.client.force_login(self.director)
        response = self.client.get(reverse('academico:opciones_seccion'),{'carrera':self.carrera.pk,'asignatura':self.materia.pk})
        self.assertEqual(response.status_code,400)
        self.assertIn('agotaron',response.json()['error'])
        response = self.client.post(reverse('academico:crear_curso'),{'carrera':self.carrera.pk,'asignatura_catalogo':self.materia.pk,'turno':'false','docentes':[self.profesor.pk]})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'agotaron')

    def test_admin_asigna_varias_asignaturas_y_sincroniza_curso(self):
        adicional = Curso.objects.create(asignatura_catalogo=self.materia,turno=False)
        self.client.force_login(self.admin)
        url = reverse('admin:academico_estudiante_change',args=[self.perfil.pk])
        datos = {'usuario':self.alumno.pk,'rut_estudiante':self.perfil.rut_estudiante,'nombre_completo':self.perfil.nombre_completo,'carrera':self.carrera.pk,'secciones':[self.seccion.pk,adicional.pk],'_save':'Guardar'}
        self.assertEqual(self.client.post(url,datos).status_code,302)
        self.perfil.refresh_from_db();self.alumno.refresh_from_db()
        self.assertSetEqual(set(self.perfil.secciones.values_list('pk',flat=True)),{self.seccion.pk,adicional.pk})
        self.assertEqual(self.alumno.curso_id,self.perfil.curso_id)
        ajena = Curso.objects.create(asignatura_catalogo=self.ajena,turno=True)
        response = self.client.post(url,{**datos,'secciones':[ajena.pk]})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'deben pertenecer a la carrera')
        self.assertSetEqual(set(self.perfil.secciones.values_list('pk',flat=True)),{self.seccion.pk,adicional.pk})
        self.assertContains(self.client.get(reverse('admin:usuarios_usuario_changelist')),'Asignar asignaturas / secciones')

    def test_asistencia_muestra_rut_y_guarda_hora_automatica_sin_duplicar(self):
        self.client.force_login(self.profesor)
        url = reverse('academico:tomar_asistencia')
        self.assertContains(self.client.get(url),'Nombre completo')
        self.assertContains(self.client.get(url),'>RUT<')
        datos = {'curso':self.seccion.pk,f'estado_{self.perfil.pk}':'presente','fecha':'1900-01-01'}
        with patch('academico.views.avisar_estudiante') as publicar, self.captureOnCommitCallbacks(execute=True):
            response=self.client.post(url,datos)
        self.assertEqual(publicar.call_count,1)
        self.assertRedirects(response,url)
        self.assertTrue(MarcaAsistencia.objects.get().presente)
        self.assertTrue(RegistroAsistencia.objects.get().presente)
        self.assertEqual(RegistroAsistencia.objects.get().seccion_id,self.seccion.pk)
        self.assertEqual(SesionClase.objects.get().fecha,timezone.localdate())
        texto=' '.join(str(m) for m in get_messages(response.wsgi_request))
        self.assertRegex(texto,r'\d{2}-\d{2}--\d{2}/\d{2}/\d{4}')
        self.client.post(url,datos)
        self.assertEqual(AvisoAsistencia.objects.count(),1)
        self.client.post(url,{**datos,f'estado_{self.perfil.pk}':'ausente'})
        self.assertFalse(MarcaAsistencia.objects.get().presente)
        self.assertFalse(RegistroAsistencia.objects.get().presente)
        self.assertEqual(SesionClase.objects.count(),1)
        self.assertEqual(RegistroAsistencia.objects.count(),1)
        self.assertEqual(AvisoAsistencia.objects.count(),2)
        alumnos=self.client.get(reverse('academico:ajax_cargar_estudiantes'),{'curso_id':self.seccion.pk}).json()
        self.assertEqual(alumnos[0]['rut'],self.alumno.rut)
        self.assertIs(alumnos[0]['presente'],False)
        self.assertRegex(alumnos[0]['fecha_registro'],r'^\d{2}-\d{2}--\d{2}/\d{2}/\d{4}$')

    def test_asistencia_incompleta_no_guarda_y_estudiante_no_puede_editar(self):
        self.client.force_login(self.profesor)
        self.client.post(reverse('academico:tomar_asistencia'),{'curso':self.seccion.pk})
        self.assertFalse(SesionClase.objects.exists())
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.get(reverse('academico:tomar_asistencia')).status_code,403)
        self.assertEqual(self.client.get(reverse('academico:ajax_cargar_estudiantes'),{'curso_id':self.seccion.pk}).status_code,403)

    def test_registro_admin_abre_el_formulario_de_asistencia(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse('admin:academico_registroasistencia_add')),reverse('academico:tomar_asistencia'))

    def test_observaciones_restringidas_por_autor_y_rol(self):
        obs=ObservacionComportamiento.objects.create(docente=self.profesor,curso=self.seccion,asunto='Caso',descripcion='Texto',tipo_observacion='SANCION')
        obs.estudiantes.add(self.perfil)
        url=reverse('academico:actualizar_observacion',args=[obs.pk])
        for rol,estado in [('estudiante',403),('docente',404)]:
            intruso=Usuario.objects.create_user(rut='71000000-'+str(estado),rol=rol)
            self.client.force_login(intruso)
            self.assertEqual(self.client.get(url).status_code,estado)
            self.assertEqual(self.client.post(url,{'tipo_observacion':'SANCION','estado':'RESUELTA','notificar_apoderado':'on'}).status_code,estado)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.get(url).status_code,200)
        otro=Usuario.objects.create_user(rut='72000000-1',rol='docente')
        self.client.force_login(otro)
        response=self.client.post(reverse('academico:crear_observacion'),{'curso':self.seccion.pk,'estudiantes':[self.perfil.pk],'tipo_observacion':'SANCION','asunto':'Intruso','descripcion':'Texto'})
        self.assertEqual(response.status_code,200)
        self.assertIn('curso',response.context['form'].errors)
        self.assertEqual(ObservacionComportamiento.objects.count(),1)

    def test_migracion_historica_respeta_correcciones_y_no_duplica(self):
        fecha=timezone.now()-timedelta(days=3)
        antiguo=RegistroAsistencia.objects.create(estudiante=self.perfil,docente=self.profesor,presente=True)
        RegistroAsistencia.objects.filter(pk=antiguo.pk).update(fecha=fecha)
        ultimo=RegistroAsistencia.objects.create(estudiante=self.perfil,docente=self.profesor,presente=False)
        RegistroAsistencia.objects.filter(pk=ultimo.pk).update(fecha=fecha+timedelta(minutes=5))
        importar=import_module('academico.migrations.0015_migrar_asistencia_historica').importar_historial
        importar(apps,SimpleNamespace(connection=connection))
        self.assertEqual(MarcaAsistencia.objects.count(),1)
        self.assertFalse(MarcaAsistencia.objects.get().presente)
        self.assertEqual(SesionClase.objects.get().fecha,timezone.localtime(fecha).date())
        self.assertEqual(RegistroAsistencia.objects.count(),2)
        self.assertFalse(RegistroAsistencia.objects.filter(seccion__isnull=True).exists())
        importar(apps,SimpleNamespace(connection=connection))
        self.assertEqual(MarcaAsistencia.objects.count(),1)
        self.assertFalse(AvisoAsistencia.objects.exists())

    def test_historial_moderno_tiene_prioridad_y_origen_ambiguo_se_conserva(self):
        fecha = timezone.localdate() - timedelta(days=2)
        sesion = SesionClase.objects.create(seccion=self.seccion, fecha=fecha, docente=self.profesor)
        MarcaAsistencia.objects.create(sesion=sesion, estudiante=self.perfil, presente=True)
        antiguo = RegistroAsistencia.objects.create(estudiante=self.perfil, docente=self.profesor, presente=False)
        instante = timezone.now() - timedelta(days=2)
        RegistroAsistencia.objects.filter(pk=antiguo.pk).update(fecha=instante)
        sin_curso = Estudiante.objects.create(rut_estudiante='73000000-1', nombre_completo='Sin sección')
        ambiguo = RegistroAsistencia.objects.create(estudiante=sin_curso, docente=self.profesor, presente=False)
        importar = import_module('academico.migrations.0015_migrar_asistencia_historica').importar_historial
        importar(apps, SimpleNamespace(connection=connection))
        self.assertTrue(MarcaAsistencia.objects.get().presente)
        self.assertEqual(MarcaAsistencia.objects.count(), 1)
        self.assertTrue(RegistroAsistencia.objects.filter(pk=ambiguo.pk, seccion__isnull=True).exists())

    async def test_websocket_restringe_rol_y_no_envia_avisos_a_otro_estudiante(self):
        from channels.testing import WebsocketCommunicator
        from channels.layers import get_channel_layer
        from .consumers import AvisosEstudianteConsumer
        from django.contrib.auth.models import AnonymousUser
        for usuario in (AnonymousUser(), self.profesor):
            canal = WebsocketCommunicator(AvisosEstudianteConsumer.as_asgi(), '/ws/avisos/estudiante/')
            canal.scope['user'] = usuario
            conectado, codigo = await canal.connect()
            self.assertFalse(conectado)
            self.assertEqual(codigo, 4403)
            await canal.disconnect()
        primero = WebsocketCommunicator(AvisosEstudianteConsumer.as_asgi(), '/ws/avisos/estudiante/')
        primero.scope['user'] = self.alumno
        segundo = WebsocketCommunicator(AvisosEstudianteConsumer.as_asgi(), '/ws/avisos/estudiante/')
        # Una identidad diferente no debe recibir el aviso de la primera.
        segundo.scope['user'] = SimpleNamespace(is_authenticated=True, rol='estudiante', pk=999999)
        self.assertTrue((await primero.connect())[0])
        self.assertTrue((await segundo.connect())[0])
        await get_channel_layer().group_send(f'estudiante_{self.alumno.pk}', {'type':'alerta.asistencia','aviso_id':123,'texto':'Aviso privado'})
        self.assertEqual((await primero.receive_json_from())['texto'], 'Aviso privado')
        self.assertTrue(await segundo.receive_nothing(timeout=0.03))
        await primero.disconnect()
        await segundo.disconnect()

    def test_creacion_permite_todas_las_carreras_y_numero_inicial_real(self):
        self.client.force_login(self.director)
        response = self.client.get(reverse('academico:home_administrativo'))
        form = response.context['curso_form']
        self.assertSetEqual(set(form.fields['carrera'].queryset.values_list('pk', flat=True)), set(Carrera.objects.values_list('pk', flat=True)))
        self.assertEqual(form.numero_seccion, '001')
        self.assertEqual(form.codigo_seccion, 'MAT-001-D')
        self.assertContains(response, 'value="001" readonly')
        datos = {'carrera':self.otra.pk,'asignatura_catalogo':self.ajena.pk,'turno':'false','docentes':[self.profesor.pk]}
        self.assertEqual(self.client.post(reverse('academico:crear_curso'),datos).status_code,302)
        creada = Curso.objects.get(asignatura_catalogo=self.ajena)
        self.assertEqual(creada.seccion, 'HIS-000-V')
        opcion = self.client.get(reverse('academico:opciones_seccion'),{'carrera':self.otra.pk,'asignatura':self.ajena.pk})
        self.assertEqual(opcion.json()['numero'],'001')
