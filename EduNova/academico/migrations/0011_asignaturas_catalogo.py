from django.db import migrations, models
import django.db.models.deletion

DATOS = [('Ingeniería en Informática', 'https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1446115-2024-Ingenieroa-en-Informa%CC%81tica.pdf', [('FPY1101', 'Fundamentos de Programación'), ('DSY1101', 'Introducción a Cloud Computing'), ('MAT1111', 'Nivelación Matemática')]), ('Ingeniería en Infraestructura Tecnológica', 'https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1446815-2024-Ingenieroa-en-Infraestructura-Tecnolo%CC%81gica-PRESENCIAL.pdf', [('INY1102', 'Fundamentos Cloud I'), ('BIY1101', 'Bases de Innovación'), ('ADY1101', 'Sistemas Operativos I')]), ('Ingeniería en Redes y Telecomunicaciones', 'https://www.duoc.cl/wp-content/uploads/2025/09/Malla-Curricular-1445101-2025-Ingenieroa-en-Redes-y-Telecomunicaciones.pdf', [('AYV1101', 'Introducción a las Telecomunicaciones'), ('AYV1182', 'Soporte Computacional IT Essentials'), ('AYV1108', 'Conectividad de Redes')]), ('Administración en Turismo y Hospitalidad', 'https://www.duoc.cl/wp-content/uploads/2025/10/ATH_mencio%CC%81n-Administracio%CC%81n-Hotelera_diploma-Hoteleri%CC%81a.pdf', [('NHT1101', 'Ecosistema de la Industria Turística'), ('NHT1102', 'Mindset Turismo y Hospitalidad'), ('MCT1201', 'Marketing y Comercialización para Turismo y Hotelería')]), ('Ingeniería en Marketing Digital', 'https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1116216-2023-Ingeniero-en-Marketing-Digital-PRESENCIAL.pdf', [('MKA1101', 'Introducción al Marketing'), ('VNA1101', 'Fundamentos de Ventas'), ('ANA1201', 'Fundamentos de Economía')]), ('Auditoría', 'https://www.duoc.cl/wp-content/uploads/2026/01/Malla-Curricular-1117101-2026-Contadora-Auditora-Auditori%CC%81a-y-ana%CC%81lisis-de-negocios-FOL.pdf', [('TRA1100', 'Legislación Tributaria'), ('CCA1101', 'Contabilidad I'), ('FNA1101', 'Administración y Economía')]), ('Ingeniería en Gestión Logística', 'https://www.duoc.cl/wp-content/uploads/2024/10/6-ING-GESTION-LOGISTICA.pdf', [('LOG-INTRO', 'Introducción a la Logística'), ('LOG-TRANS', 'Operaciones de Transporte'), ('LOG-ALMAC', 'Operaciones de Almacenamiento')]), ('Ingeniería en Comercio Exterior', 'https://malla.duoc.cl/malla/administracion-negocios/011-ing-comercio-exterior.html', [('ABA1101', 'Introducción al Comercio Exterior'), ('ABA1102', 'Introducción a la Logística'), ('GAA1101', 'Herramientas Tecnológicas I')]), ('Ingeniería en Administración Mención Gestión de Personas', 'https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1116415-2024-Ingenieroa-en-Administracio%CC%81n-mencio%CC%81n-Gestio%CC%81n-de-Personas-PRESENCIAL.pdf', [('LCA0121', 'Fundamentos de Contabilidad'), ('GEA1101', 'Normas y Procedimientos'), ('GEA1108', 'Fundamentos de Economía')]), ('Ingeniería en Administración Mención Innovación y Emprendimiento', 'https://www.duoc.cl/wp-content/uploads/2025/10/Malla-Curricular-1116711-2024-Ingenieroa-en-Administracio%CC%81n-mencio%CC%81n-Innovacio%CC%81n-y-Emprendimiento-PRESENCIAL.pdf', [('LCA8121', 'Fundamentos de Contabilidad'), ('GEA1811', 'Normas y Procedimientos'), ('GEA1808', 'Fundamentos de Economía')]), ('Ingeniería en Administración Mención Finanzas', 'https://malla.duoc.cl/malla/administracion-negocios/007-ing-administracion-m-finanzas.html', [('LCA0121', 'Fundamentos de Contabilidad'), ('GEA1101', 'Normas y Procedimientos'), ('GEA1108', 'Fundamentos de Economía')]), ('Técnico en Administración', 'https://www.duoc.cl/wp-content/uploads/2025/09/Malla-Curricular-1111212-2024-Tecnico-en-Administracion.pdf', [('LCA0121', 'Fundamentos de Contabilidad'), ('GEA1101', 'Normas y Procedimientos'), ('GEA1108', 'Fundamentos de Economía')]), ('Gastronomía Internacional', 'https://www.duoc.cl/wp-content/uploads/2025/09/Malla-Curricular-667017-2024-Gastronomia-Internacional.pdf', [('GAS-COC', 'Cocina Básica'), ('GAS-PAN', 'Panadería'), ('GAS-HIG', 'Higiene y Prevención de Riesgos')])]


def cargar_catalogo(apps, schema_editor):
    Carrera = apps.get_model('academico', 'Carrera')
    Asignatura = apps.get_model('academico', 'Asignatura')
    Relacion = apps.get_model('academico', 'CarreraAsignatura')
    Curso = apps.get_model('academico', 'Curso')
    db = schema_editor.connection.alias
    for nombre_carrera, fuente, asignaturas in DATOS:
        carrera = Carrera.objects.using(db).filter(nombre=nombre_carrera).first()
        if not carrera:
            continue
        for codigo, nombre in asignaturas:
            asignatura, _ = Asignatura.objects.using(db).get_or_create(
                codigo=codigo, defaults={'nombre': nombre})
            Relacion.objects.using(db).get_or_create(
                carrera_id=carrera.pk, asignatura_id=asignatura.pk,
                defaults={'fuente_malla': fuente})
            # Asociar secciones ya existentes por nombre sin modificarlas ni duplicarlas.
            Curso.objects.using(db).filter(asignatura__iexact=nombre, asignatura_catalogo__isnull=True).update(asignatura_catalogo_id=asignatura.pk)


class Migration(migrations.Migration):
    dependencies = [('academico', '0010_carreras_matriculas')]
    operations = [
        migrations.CreateModel(name='Asignatura', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('codigo', models.CharField(max_length=24, unique=True)),
            ('nombre', models.CharField(max_length=180)),
            ('activa', models.BooleanField(default=True)),
        ], options={'ordering': ['nombre', 'codigo'], 'verbose_name': 'Asignatura de catálogo', 'verbose_name_plural': 'Asignaturas de catálogo'}),
        migrations.CreateModel(name='CarreraAsignatura', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('carrera', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='malla',to='academico.carrera')),
            ('asignatura', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='planes',to='academico.asignatura')),
            ('fuente_malla', models.URLField(blank=True)),
        ],options={'verbose_name':'Asignatura de una carrera', 'verbose_name_plural':'Mallas de carreras'}),
        migrations.AddField(model_name='asignatura',name='carreras',field=models.ManyToManyField(related_name='asignaturas',through='academico.CarreraAsignatura',to='academico.carrera')),
        migrations.AddField(model_name='curso',name='asignatura_catalogo',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='secciones',to='academico.asignatura')),
        migrations.AddConstraint(model_name='carreraasignatura',constraint=models.UniqueConstraint(fields=['carrera','asignatura'],name='uq_carrera_asignatura')),
        migrations.RunPython(cargar_catalogo, migrations.RunPython.noop),
    ]
