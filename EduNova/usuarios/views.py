from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import LoginForm, RegistroForm
from .models import Usuario


def login_view(request):
    if request.user.is_authenticated:
        return redirect('usuarios:post_login_redirect')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        rut = form.cleaned_data['rut'].strip().upper().replace('.', '')
        password = form.cleaned_data['password']
        user = authenticate(request, username=rut, password=password)
        if user is not None:
            login(request, user)
            return redirect('usuarios:post_login_redirect')
        messages.error(request, 'RUT o contraseña incorrectos.')

    return render(request, 'usuarios/login.html', {'form': form})


def registro_view(request):
    if request.user.is_authenticated:
        return redirect('usuarios:post_login_redirect')

    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        login(request, usuario)
        messages.success(request, f'¡Bienvenido/a a EduNova, {usuario.first_name}!')
        return redirect('usuarios:post_login_redirect')

    return render(request, 'usuarios/registro.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('usuarios:login')


@login_required
def post_login_redirect(request):
    """Deriva al home correspondiente según el rol del usuario autenticado."""
    if request.user.rol == Usuario.Rol.DOCENTE:
        return redirect('academico:home_docente')
    elif request.user.rol == Usuario.Rol.APODERADO:
        return redirect('academico:home_apoderado')
    elif request.user.rol == Usuario.Rol.ADMINISTRADOR:
        messages.info(request, 'Aún no existe un panel propio para Administrador; usa /admin/ por ahora.')
        return redirect('admin:index')
    elif request.user.rol == Usuario.Rol.ADMINISTRATIVO:
        return redirect('academico:home_administrativo')
    messages.info(request, 'Tu tipo de cuenta aún no tiene un panel asignado.')
    return redirect('usuarios:login')
