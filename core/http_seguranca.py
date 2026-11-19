"""Transporte de credenciais sem redirecionamento ou eco de segredos."""
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.parse import urlsplit


class SemRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def abrir(req, timeout):
    return build_opener(SemRedirect()).open(req, timeout=timeout)


def validar_endpoint(url):
    partes = urlsplit(str(url))
    if (partes.scheme not in ('http', 'https') or not partes.hostname
            or partes.username or partes.password or partes.query or partes.fragment):
        raise ValueError('URL inválida: informe http(s), sem credenciais, consulta ou fragmento')
    return str(url).rstrip('/')


def sanitizar(texto, segredo=''):
    return str(texto).replace(segredo, '[oculto]') if segredo else str(texto)
