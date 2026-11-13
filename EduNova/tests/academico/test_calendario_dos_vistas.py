"""Regresión de estructura del calendario compacto y ampliado, sin base de datos."""
from datetime import time
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class CalendarioCompactoAmpliadoTests(SimpleTestCase):
    def test_mismo_calendario_conserva_actividades_y_navegacion(self):
        clase = SimpleNamespace(
            asignatura='Desarrollo Web', inicio=time(8, 30), fin=time(9, 50),
            sala='301', docente='Docente Ejemplo',
        )
        reunion = SimpleNamespace(
            tipo='reunion', titulo='Reunión de coordinación',
            descripcion='Revisar acuerdos', hora_inicio=time(10, 5),
            hora_fin=time(11, 5), get_tipo_display=lambda: 'Reunión',
        )
        tarea = SimpleNamespace(
            tipo_actividad='evaluacion', titulo='Evaluación 3',
            descripcion='Control de programación', hora_inicio=time(12, 7),
            prioridad='alta', completada=False,
            get_tipo_actividad_display=lambda: 'Evaluación',
        )
        dia = SimpleNamespace(numero=17, es_hoy=False,
                              clases=[clase], eventos=[reunion], tareas=[tarea])
        vacio = SimpleNamespace(numero=18, es_hoy=False, clases=[], eventos=[], tareas=[])
        html = render_to_string('academico/_calendario.html', {
            'mes_nombre': 'Noviembre', 'anio': 2026, 'mes': 11,
            'prev_year': 2026, 'prev_month': 10,
            'next_year': 2026, 'next_month': 12,
            'semanas': [[dia, vacio]],
        })
        self.assertIn('data-edn-day="2026-11-17"', html)
        self.assertIn('data-edn-day="2026-11-18"', html)
        self.assertIn('data-kind="clase"', html)
        self.assertIn('data-kind="reunion"', html)
        self.assertIn('data-kind="evaluacion"', html)
        self.assertIn('08:30–09:50', html)
        self.assertIn('Sala: 301', html)
        self.assertIn('Docente Ejemplo', html)
        self.assertIn('Reunión de coordinación', html)
        self.assertIn('Evaluación 3', html)
        self.assertIn('edn-calendar-detail', html)
        self.assertIn('hx-get="?year=2026&month=10"', html)
        self.assertIn('hx-get="?year=2026&month=12"', html)
        self.assertIn('hx-select=".calendario-scroll"', html)
        self.assertIn('calendario-redisenado.js', html)
        self.assertIn('calendario-redisenado.css', html)
