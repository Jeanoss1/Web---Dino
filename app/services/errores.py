class ErrorNegocio(Exception):
    """Error esperado de una regla de negocio; el mensaje se muestra al usuario."""

    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
