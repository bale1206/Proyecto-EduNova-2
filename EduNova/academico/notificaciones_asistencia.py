import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def avisar_estudiante(usuario_id, aviso_id, texto):
    """Entrega inmediata opcional; el aviso ya fue persistido antes de llamar."""
    try:
        layer = get_channel_layer()
        if layer is not None:
            async_to_sync(layer.group_send)(f'estudiante_{usuario_id}', {
                'type':'alerta.asistencia', 'aviso_id':aviso_id, 'texto':texto,
            })
    except Exception:
        logger.exception('No se pudo publicar el aviso en tiempo real')
