import qrcode

def gerar_qrcode(texto, caminho_saida):
    img = qrcode.make(texto)
    img.save(caminho_saida)
    return caminho_saida
