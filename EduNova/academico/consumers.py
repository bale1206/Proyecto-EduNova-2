from channels.generic.websocket import AsyncJsonWebsocketConsumer


class AvisosEstudianteConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated or user.rol != 'estudiante':
            await self.close(code=4403)
            return
        self.grupo = f'estudiante_{user.pk}'
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'grupo'):
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def alerta_asistencia(self, event):
        await self.send_json({'tipo':'asistencia', 'id':event['aviso_id'], 'texto':event['texto']})
