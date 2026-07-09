"""Popula o banco com um catálogo de 100 sites em português e seus seletores.

Cada site recebe entre 5 e 8 seletores derivados de um template por categoria
(notícias, e-commerce, finanças, clima, governo, etc.), cobrindo campos comuns:
título, autor, preço, data, links, imagens, disponibilidade, etc.

ATENÇÃO: este é um catálogo de PARTIDA, não validado ao vivo. Rode
`python manage.py check_selectors` em seguida — os seletores que falharem
geram ChangeEvents e alimentam o módulo de recomendação via LLM.

Idempotente: rodar novamente não duplica sites nem seletores.
"""
from django.core.management.base import BaseCommand

from monitor.models import Selector, Site

# ── Templates de seletores por categoria ──────────────────────────────
# (nome, seletor, tipo, tipo_esperado, min_results)

NOTICIAS = [
    ("Manchete principal", "h1", "css", "text", 1),
    ("Títulos de notícias", "h2 a", "css", "text", 1),
    ("Chamadas de matéria", "article p", "css", "text", 1),
    ("Data/hora", "time", "css", "text", 1),
    ("Menu de seções", "nav a", "css", "text", 1),
    ("Links de matérias", "//h2/a/@href", "xpath", "url", 1),
    ("Imagens de destaque", "//img/@src", "xpath", "url", 1),
]

FINANCAS = [
    ("Manchete principal", "h1", "css", "text", 1),
    ("Títulos de notícias", "h2 a", "css", "text", 1),
    ("Chamadas", "article p", "css", "text", 1),
    ("Data/hora", "time", "css", "text", 1),
    ("Menu de seções", "nav a", "css", "text", 1),
    ("Links de matérias", "//h2/a/@href", "xpath", "url", 1),
]

ECOMMERCE = [
    ("Nome do produto", "h1", "css", "text", 1),
    ("Preço", ".price", "css", "number", 1),
    ("Preço parcelado", ".installment", "css", "text", 1),
    ("Disponibilidade", ".availability", "css", "text", 1),
    ("Marca", ".brand", "css", "text", 1),
    ("Avaliação", ".rating", "css", "text", 1),
    ("Link do produto", "//a/@href", "xpath", "url", 1),
    ("Imagem do produto", "//img/@src", "xpath", "url", 1),
]

ESPORTES = [
    ("Manchete principal", "h1", "css", "text", 1),
    ("Títulos de notícias", "h2 a", "css", "text", 1),
    ("Chamadas", "article p", "css", "text", 1),
    ("Placar/tempo", "time", "css", "text", 1),
    ("Menu de seções", "nav a", "css", "text", 1),
    ("Links de matérias", "//h2/a/@href", "xpath", "url", 1),
]

CLIMA = [
    ("Cidade", "h1", "css", "text", 1),
    ("Temperatura atual", ".temperature", "css", "number", 1),
    ("Condição do tempo", ".condition", "css", "text", 1),
    ("Temperatura mínima", ".min", "css", "number", 1),
    ("Temperatura máxima", ".max", "css", "number", 1),
]

GOVERNO = [
    ("Título da página", "h1", "css", "text", 1),
    ("Notícias/publicações", "h2 a", "css", "text", 1),
    ("Chamadas", "article p", "css", "text", 1),
    ("Data", "time", "css", "text", 1),
    ("Menu", "nav a", "css", "text", 1),
    ("Links", "//a/@href", "xpath", "url", 1),
]

TECNOLOGIA = NOTICIAS
CULTURA = [
    ("Título principal", "h1", "css", "text", 1),
    ("Títulos de posts", "h2 a", "css", "text", 1),
    ("Resumos", "article p", "css", "text", 1),
    ("Autor", ".author", "css", "text", 1),
    ("Data", "time", "css", "text", 1),
    ("Links", "//h2/a/@href", "xpath", "url", 1),
    ("Imagens", "//img/@src", "xpath", "url", 1),
]

EMPREGOS = [
    ("Título da vaga", "h2 a", "css", "text", 1),
    ("Empresa", ".company", "css", "text", 1),
    ("Localização", ".location", "css", "text", 1),
    ("Salário", ".salary", "css", "number", 1),
    ("Data de publicação", "time", "css", "text", 1),
    ("Link da vaga", "//a/@href", "xpath", "url", 1),
]

REFERENCIA = [
    ("Título", "h1", "css", "text", 1),
    ("Subtítulos", "h2", "css", "text", 1),
    ("Parágrafos", "p", "css", "text", 1),
    ("Itens de lista", "li", "css", "text", 1),
    ("Links internos", "//a/@href", "xpath", "url", 1),
    ("Imagens", "//img/@src", "xpath", "url", 1),
]

TEMPLATES = {
    "noticias": NOTICIAS, "financas": FINANCAS, "ecommerce": ECOMMERCE,
    "esportes": ESPORTES, "clima": CLIMA, "governo": GOVERNO,
    "tecnologia": TECNOLOGIA, "cultura": CULTURA, "empregos": EMPREGOS,
    "referencia": REFERENCIA,
}

# ── Catálogo: (nome, url, categoria, intervalo_min) ───────────────────
SITES = [
    # A. Notícias gerais
    ("G1", "https://g1.globo.com", "noticias", 60),
    ("UOL Notícias", "https://noticias.uol.com.br", "noticias", 60),
    ("Folha de S.Paulo", "https://www.folha.uol.com.br", "noticias", 60),
    ("Estadão", "https://www.estadao.com.br", "noticias", 60),
    ("CNN Brasil", "https://www.cnnbrasil.com.br", "noticias", 60),
    ("R7", "https://noticias.r7.com", "noticias", 60),
    ("BBC News Brasil", "https://www.bbc.com/portuguese", "noticias", 60),
    ("Agência Brasil", "https://agenciabrasil.ebc.com.br", "noticias", 60),
    ("Carta Capital", "https://www.cartacapital.com.br", "noticias", 60),
    ("Nexo Jornal", "https://www.nexojornal.com.br", "noticias", 60),
    ("Metrópoles", "https://www.metropoles.com", "noticias", 60),
    ("Gazeta do Povo", "https://www.gazetadopovo.com.br", "noticias", 60),
    ("Correio Braziliense", "https://www.correiobraziliense.com.br", "noticias", 60),
    ("O Globo", "https://oglobo.globo.com", "noticias", 60),
    ("Poder360", "https://www.poder360.com.br", "noticias", 60),
    ("Brasil de Fato", "https://www.brasildefato.com.br", "noticias", 60),
    ("IstoÉ", "https://istoe.com.br", "noticias", 60),
    ("Veja", "https://veja.abril.com.br", "noticias", 60),
    ("Exame", "https://exame.com", "noticias", 60),
    ("The Intercept Brasil", "https://www.intercept.com.br", "noticias", 60),
    # B. Finanças e cotações
    ("InfoMoney", "https://www.infomoney.com.br", "financas", 30),
    ("Valor Econômico", "https://valor.globo.com", "financas", 30),
    ("Investing.com — Ibovespa", "https://br.investing.com/indices/bovespa", "financas", 30),
    ("Melhor Câmbio — Dólar", "https://www.melhorcambio.com/dolar-hoje", "financas", 30),
    ("B3", "https://www.b3.com.br/pt_br/", "financas", 60),
    ("Banco Central", "https://www.bcb.gov.br", "financas", 60),
    ("Suno Notícias", "https://www.suno.com.br/noticias/", "financas", 30),
    ("Money Times", "https://www.moneytimes.com.br", "financas", 30),
    ("Seu Dinheiro", "https://www.seudinheiro.com", "financas", 30),
    ("Investnews", "https://investnews.com.br", "financas", 30),
    ("Cointimes", "https://cointimes.com.br", "financas", 30),
    ("Livecoins", "https://livecoins.com.br", "financas", 30),
    # C. E-commerce e preços
    ("Magazine Luiza", "https://www.magazineluiza.com.br", "ecommerce", 60),
    ("Casas Bahia", "https://www.casasbahia.com.br", "ecommerce", 60),
    ("Americanas", "https://www.americanas.com.br", "ecommerce", 60),
    ("Submarino", "https://www.submarino.com.br", "ecommerce", 60),
    ("Kabum!", "https://www.kabum.com.br", "ecommerce", 60),
    ("Netshoes", "https://www.netshoes.com.br", "ecommerce", 60),
    ("Centauro", "https://www.centauro.com.br", "ecommerce", 60),
    ("Fast Shop", "https://www.fastshop.com.br", "ecommerce", 60),
    ("Livraria da Travessa", "https://www.travessa.com.br", "ecommerce", 60),
    ("Saraiva", "https://www.saraiva.com.br", "ecommerce", 60),
    ("Amazon Brasil", "https://www.amazon.com.br", "ecommerce", 60),
    ("Extra", "https://www.extra.com.br", "ecommerce", 60),
    ("Ponto (Ponto Frio)", "https://www.pontofrio.com.br", "ecommerce", 60),
    # D. Esportes
    ("Globo Esporte", "https://ge.globo.com", "esportes", 60),
    ("Lance!", "https://www.lance.com.br", "esportes", 60),
    ("UOL Esporte", "https://www.uol.com.br/esporte/", "esportes", 60),
    ("ESPN Brasil", "https://www.espn.com.br", "esportes", 60),
    ("Gazeta Esportiva", "https://www.gazetaesportiva.com", "esportes", 60),
    ("Trivela", "https://trivela.com.br", "esportes", 60),
    ("Placar", "https://placar.abril.com.br", "esportes", 60),
    ("CBF", "https://www.cbf.com.br", "esportes", 60),
    ("Terra Esportes", "https://www.terra.com.br/esportes/", "esportes", 60),
    ("Máquina do Esporte", "https://maquinadoesporte.com.br", "esportes", 60),
    # E. Clima e tempo
    ("Climatempo — SP", "https://www.climatempo.com.br/previsao-do-tempo/cidade/558/saopaulo-sp", "clima", 30),
    ("INMET", "https://portal.inmet.gov.br", "clima", 60),
    ("Tempo Agora", "https://www.tempoagora.com.br", "clima", 30),
    ("Clima ao Vivo", "https://www.climaaovivo.com.br", "clima", 30),
    ("Somar Meteorologia", "https://www.somarmeteorologia.com.br", "clima", 60),
    # F. Governo e dados públicos
    ("Portal gov.br", "https://www.gov.br/pt-br", "governo", 120),
    ("Planalto", "https://www.planalto.gov.br", "governo", 120),
    ("IBGE", "https://www.ibge.gov.br", "governo", 120),
    ("Câmara dos Deputados", "https://www.camara.leg.br", "governo", 120),
    ("Senado Federal", "https://www12.senado.leg.br", "governo", 120),
    ("STF", "https://portal.stf.jus.br", "governo", 120),
    ("STJ", "https://www.stj.jus.br", "governo", 120),
    ("TSE", "https://www.tse.jus.br", "governo", 120),
    ("Receita Federal", "https://www.gov.br/receitafederal/pt-br", "governo", 120),
    ("Portal da Transparência", "https://www.portaltransparencia.gov.br", "governo", 120),
    ("Diário Oficial da União", "https://www.in.gov.br", "governo", 120),
    ("Ministério da Saúde", "https://www.gov.br/saude/pt-br", "governo", 120),
    # G. Tecnologia
    ("Tecnoblog", "https://tecnoblog.net", "tecnologia", 60),
    ("Olhar Digital", "https://olhardigital.com.br", "tecnologia", 60),
    ("Canaltech", "https://canaltech.com.br", "tecnologia", 60),
    ("TecMundo", "https://www.tecmundo.com.br", "tecnologia", 60),
    ("Adrenaline", "https://www.adrenaline.com.br", "tecnologia", 60),
    ("Meio Bit", "https://meiobit.com", "tecnologia", 60),
    ("Hardware.com.br", "https://www.hardware.com.br", "tecnologia", 60),
    ("Showmetech", "https://www.showmetech.com.br", "tecnologia", 60),
    # H. Cultura e entretenimento
    ("Omelete", "https://www.omelete.com.br", "cultura", 60),
    ("AdoroCinema", "https://www.adorocinema.com", "cultura", 60),
    ("Legião dos Heróis", "https://www.legiaodosherois.com.br", "cultura", 60),
    ("Rolling Stone Brasil", "https://rollingstone.com.br", "cultura", 60),
    ("Tenho Mais Discos que Amigos", "https://www.tmdqa.com", "cultura", 60),
    ("Jovem Nerd", "https://jovemnerd.com.br", "cultura", 60),
    ("Cifra Club", "https://www.cifraclub.com.br", "cultura", 60),
    ("Skoob", "https://www.skoob.com.br", "cultura", 60),
    # I. Empregos e concursos
    ("Vagas.com", "https://www.vagas.com.br", "empregos", 120),
    ("Catho", "https://www.catho.com.br", "empregos", 120),
    ("InfoJobs", "https://www.infojobs.com.br", "empregos", 120),
    ("PCI Concursos", "https://www.pciconcursos.com.br", "empregos", 120),
    ("Gran Cursos", "https://blog.grancursosonline.com.br", "empregos", 120),
    # J. Referência e educação
    ("Wikipédia PT — Brasil", "https://pt.wikipedia.org/wiki/Brasil", "referencia", 240),
    ("Wikcionário PT — casa", "https://pt.wiktionary.org/wiki/casa", "referencia", 240),
    ("Brasil Escola", "https://brasilescola.uol.com.br", "referencia", 120),
    ("Mundo Educação", "https://mundoeducacao.uol.com.br", "referencia", 120),
    ("Toda Matéria", "https://www.todamateria.com.br", "referencia", 120),
    ("Só Português", "https://www.soportugues.com.br", "referencia", 120),
    ("Dicio — casa", "https://www.dicio.com.br/casa/", "referencia", 240),
]


class Command(BaseCommand):
    help = "Popula o banco com 100 sites em português e seus seletores (catálogo de partida)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Mostra o que seria criado sem gravar no banco")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        sites_new = sels_new = sels_skip = 0

        for name, url, category, interval in SITES:
            template = TEMPLATES[category]

            if dry:
                self.stdout.write(f"[SITE] {name} ({category}) — {len(template)} seletores")
                sites_new += 1
                sels_new += len(template)
                continue

            site, created = Site.objects.get_or_create(
                url=url,
                defaults={"name": name, "check_interval_minutes": interval},
            )
            if created:
                sites_new += 1

            for sname, selector, stype, expected, minr in template:
                _, s_created = Selector.objects.get_or_create(
                    site=site, name=sname,
                    defaults={
                        "selector": selector, "selector_type": stype,
                        "expected_type": expected, "min_results": minr,
                    },
                )
                if s_created:
                    sels_new += 1
                else:
                    sels_skip += 1

        prefix = "[DRY-RUN] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"\n{prefix}{sites_new} site(s) novo(s), {sels_new} seletor(es) criado(s), "
            f"{sels_skip} já existente(s)."
        ))
        if not dry:
            self.stdout.write(
                "Próximo passo: python manage.py check_selectors "
                "(seletores que falharem geram eventos para o LLM)."
            )
