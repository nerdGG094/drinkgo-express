# Comanda Digital — Arquitetura completa

> Documentação visual do sistema (DrinkGO / Chopp Palazzo Express)
> Versão atual do código em `c:\Users\Administrador\Desktop\python\comanda_digital_v3_full`

## Sumário

1. [Visão geral do sistema](#1-visão-geral-do-sistema)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Estrutura de pastas e módulos](#3-estrutura-de-pastas-e-módulos)
4. [Modelos de dados (ERD)](#4-modelos-de-dados-erd)
5. [Sistema de autenticação e sessão](#5-sistema-de-autenticação-e-sessão)
6. [Sistema de permissões (RBAC + override)](#6-sistema-de-permissões-rbac--override)
7. [Mapa de rotas](#7-mapa-de-rotas)
8. [Fluxo de pedido (mesa / retirada / delivery)](#8-fluxo-de-pedido)
9. [Estados do pedido](#9-estados-do-pedido)
10. [Estados da mesa e da chopeira](#10-estados-da-mesa-e-da-chopeira)
11. [Aluguel de chopeiras](#11-aluguel-de-chopeiras)
12. [Pagamento e geração do cupom (com Pix)](#12-pagamento-e-geração-do-cupom)
13. [Inventário (contagem diária)](#13-inventário-contagem-diária)
14. [Relatórios e exportações](#14-relatórios-e-exportações)
15. [Migrações automáticas no boot](#15-migrações-automáticas-no-boot)
16. [Persistência externa (db / fotos / chave pix / secret key)](#16-persistência-externa)
17. [Build e deploy (PyInstaller + Launcher)](#17-build-e-deploy)
18. [Rede local (mDNS + IP + NetBIOS)](#18-rede-local)
19. [Sidebar e ícones](#19-sidebar-e-ícones)

---

## 1. Visão geral do sistema

```mermaid
graph TB
    subgraph Loja["LOJA — Rede local sem servidor dedicado"]
        Maquina["💻 Máquina principal<br/>(roda DrinkGO.exe)"]
        Tablet1["📱 Tablet 1<br/>Garçom"]
        Tablet2["📱 Tablet 2<br/>Caixa"]
        Tablet3["📱 Tablet 3<br/>Admin"]
        Roteador{{"🛜 Roteador Wi-Fi"}}
    end

    subgraph DrinkGO["DrinkGO.exe (na máquina principal)"]
        GUI["Janela Tkinter<br/>(IP, mDNS, QR)"]
        FlaskApp["Flask + SocketIO<br/>:5020"]
        SQLite[("comanda.db<br/>SQLite")]
        Uploads[("uploads/<br/>fotos")]
        Pix[(".secret_key<br/>pix_settings.json")]
    end

    Tablet1 --> Roteador
    Tablet2 --> Roteador
    Tablet3 --> Roteador
    Roteador --> Maquina
    Maquina --- DrinkGO
    GUI -.thread.-> FlaskApp
    FlaskApp --> SQLite
    FlaskApp --> Uploads
    FlaskApp --> Pix
```

---

## 2. Stack tecnológico

```mermaid
graph LR
    subgraph Backend
        Py["Python 3.12"]
        Flask["Flask 3.x"]
        SAlchemy["SQLAlchemy"]
        FLogin["Flask-Login"]
        FSocket["Flask-SocketIO"]
        Werk["Werkzeug<br/>(scrypt password)"]
        QRCode["qrcode + Pillow"]
        Pandas["pandas + openpyxl<br/>(excel export)"]
        Zeroconf["zeroconf<br/>(mDNS)"]
    end

    subgraph DB
        SQLite[("SQLite 3<br/>comanda.db")]
    end

    subgraph Frontend
        Jinja["Jinja2 templates"]
        VanillaJS["JavaScript vanilla<br/>(sem framework)"]
        ChartJS["Chart.js<br/>(dashboard)"]
        IOClient["socket.io-client"]
        CustomCSS["CSS custom<br/>1 arquivo base.css"]
    end

    subgraph Desktop
        Tk["Tkinter<br/>(launcher GUI)"]
        PyInstaller["PyInstaller<br/>(--onedir)"]
    end

    Py --> Flask
    Flask --> SAlchemy
    Flask --> FLogin
    Flask --> FSocket
    Flask --> Werk
    SAlchemy --> SQLite
    Flask --> Jinja
    Jinja --> VanillaJS
    Jinja --> ChartJS
    FSocket --> IOClient
    Tk --> Zeroconf
    Tk --> QRCode
    PyInstaller --> Tk
```

---

## 3. Estrutura de pastas e módulos

```mermaid
graph TB
    Raiz["📁 comanda_digital_v3_full/"]
    Raiz --> RunPy["run.py — entrypoint DEV"]
    Raiz --> LaunchPy["launcher.py — entrypoint EXE (GUI)"]
    Raiz --> ConfigPy["config.py — Config (PIX, sessão, db)"]
    Raiz --> BuilderTxt["Builder.txt — comando PyInstaller"]
    Raiz --> AppDir["📁 app/"]

    Raiz -. runtime .-> RuntimeFiles
    subgraph RuntimeFiles["arquivos persistentes (criados em runtime)"]
        DBFile["comanda.db"]
        SecretKey[".secret_key"]
        PixJson["pix_settings.json"]
        BackupsDir["📁 backups/"]
        UploadsDir["📁 uploads/<br/>├── produtos/<br/>└── usuarios/"]
    end

    AppDir --> Init["__init__.py — create_app, migrações, secret"]
    AppDir --> Models["models.py — SQLAlchemy ORM"]
    AppDir --> Sockets["sockets.py — SocketIO"]

    AppDir --> Auth["📁 auth/"]
    Auth --> AuthRoutes["routes.py — login/logout/perfil"]

    AppDir --> Public["📁 public/"]
    Public --> PubGarcom["garcom.py — pedidos garçom"]
    Public --> PubStatus["status.py — status pedido"]

    AppDir --> Admin["📁 admin/"]
    Admin --> AdmDashboard["dashboard.py"]
    Admin --> AdmPedidos["pedidos.py — caixa"]
    Admin --> AdmProdutos["produtos.py + categorias"]
    Admin --> AdmUsuarios["usuarios.py"]
    Admin --> AdmClientes["clientes.py"]
    Admin --> AdmChopeiras["chopeiras.py"]
    Admin --> AdmEntradas["entradas.py"]
    Admin --> AdmRel["relatorios.py + bonif_relatorio.py"]
    Admin --> AdmInv["inventario.py — contagem diária"]
    Admin --> AdmConfig["configuracao.py — chave Pix"]
    Admin --> AdmAPI["📁 api/ — JSON endpoints"]

    AppDir --> Utils["📁 utils/"]
    Utils --> UDecorators["decorators.py — role_required"]
    Utils --> UPermissoes["permissoes.py — registry + permissao_required"]
    Utils --> UPix["pix.py — BR Code + QR"]
    Utils --> UQR["qrcode_generator.py"]

    AppDir --> Templates["📁 templates/"]
    Templates --> TBase["base.html"]
    Templates --> TIcons["_icons.html — macros SVG"]
    Templates --> TAuth["📁 auth/"]
    Templates --> TAdmin["📁 admin/"]
    Templates --> TPublic["📁 public/"]
    Templates --> TErrors["📁 errors/"]

    AppDir --> Static["📁 static/"]
    Static --> CSS["css/base.css — único"]
    Static --> JS["js/* (dashboard, pedidos, chopeira, relatorios)"]
    Static --> Imagens["imagens/* (logo, favicon)"]
```

---

## 4. Modelos de dados (ERD)

```mermaid
erDiagram
    User ||--o{ Pedido : "garcom_id"
    User ||--o{ EntradaProduto : "usuario_id"
    User ||--o{ AluguelChopeira : "usuario_id"
    User ||--o{ ContagemInventario : "usuario_id"

    Mesa ||--o{ Pedido : "mesa_id"
    Cliente ||--o{ Pedido : "cliente_id"

    Pedido ||--o{ PedidoItem : "pedido_id"
    Produto ||--o{ PedidoItem : "produto_id"

    Categoria ||--o{ Produto : "categoria_id"
    Produto ||--o{ ContagemInventario : "produto_id"
    InventarioItem ||--o{ ContagemInventario : "item_id"

    Chopeira ||--o{ AluguelChopeira : "chopeira_id"

    User {
        int id PK
        string nome
        string email
        string senha_hash "scrypt"
        string role "garcom|caixa|admin"
        bool ativo
        string foto "uploads/usuarios/<file>"
        text permissoes_json "lista JSON ou NULL=defaults"
    }

    Mesa {
        int id PK
        string numero UK
        bool ativa
        string status "livre|ocupada"
    }

    Cliente {
        int id PK
        string codigo UK
        string nome
        string telefone
        string endereco
        string obs
        bool ativo
    }

    Pedido {
        int id PK
        int mesa_id FK
        int cliente_id FK
        int garcom_id FK
        string tipo "mesa|retirada|delivery"
        string cliente_nome
        string cliente_telefone
        string endereco
        string status "recebido|aberto|finalizado"
        datetime criado_em
        string forma_pagamento "dinheiro|pix|cartao|bonif|cancelado"
        string forma_pagamento2
        string tipo_cartao
        float valor_entregue
        float valor_pagamento2
        float troco
        float desconto
        bool nfe_emitida
        bool pedido_fechado
    }

    PedidoItem {
        int id PK
        int pedido_id FK
        int produto_id FK
        int quantidade
        string observacao
    }

    Produto {
        int id PK
        string nome
        int categoria_id FK
        decimal preco
        string foto
        bool ativo
        int ultima_quantidade "cache contagem"
        date ultima_contagem_data
        int alerta_se_abaixo
    }

    Categoria {
        int id PK
        string nome UK
        bool ativo
    }

    EntradaProduto {
        int id PK
        string produto_nome
        int quantidade
        text observacao
        int usuario_id FK
        datetime criado_em
    }

    Chopeira {
        int id PK
        int numero UK
        string status "disponivel|alugada"
    }

    AluguelChopeira {
        int id PK
        int chopeira_id FK
        int usuario_id FK
        string cliente_nome
        string telefone
        string endereco
        datetime data_saida
        datetime data_retorno
        string status "alugado|devolvido"
        bool alugou_co2
        string keg_tipo
        bool alugou_manometro
        bool alugou_pingadeira
    }

    InventarioItem {
        int id PK
        string nome
        string slug UK
        string categoria
        string unidade
        string icone
        text observacao
        int ultima_quantidade
        date ultima_contagem_data
        int alerta_se_abaixo
        bool ativo
        datetime criado_em
    }

    ContagemInventario {
        int id PK
        int item_id FK "OU produto_id"
        int produto_id FK "OU item_id"
        date data
        int quantidade
        string observacao
        int usuario_id FK
        datetime criado_em
    }
```

---

## 5. Sistema de autenticação e sessão

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário (tablet)
    participant B as Navegador
    participant F as Flask /auth/login
    participant DB as SQLite usuarios
    participant FL as Flask-Login

    U->>B: digita email + senha
    B->>F: POST /auth/login {email, senha}
    Note right of F: email é normalizado<br/>(strip + case-insensitive)
    F->>DB: SELECT * WHERE LOWER(email)=? AND ativo=1
    DB-->>F: User row (ou None)
    alt user encontrado E senha bate (scrypt)
        F->>FL: session.permanent = True
        F->>FL: login_user(user, remember=True)
        Note right of FL: session 30 dias<br/>remember-me cookie 60 dias<br/>SameSite=Lax, Secure=False
        F->>F: redirect role-based<br/>(garcom→novo, caixa→pedidos, admin→dashboard)
        F-->>B: 302 + Set-Cookie (session + remember_token)
        B-->>U: navegação inicial
    else senha errada / user inativo / não existe
        F-->>B: 200 render login.html<br/>flash "Usuário ou senha inválidos"
        B-->>U: tela login
    end

    Note over B,F: Cookies persistem entre reinícios do servidor<br/>graças a SECRET_KEY estável (.secret_key)
```

---

## 6. Sistema de permissões (RBAC + override)

```mermaid
flowchart TB
    Login[Login OK]
    CheckRole{role do usuário?}
    Admin[role = admin]
    NaoAdmin[role = caixa ou garcom]

    Login --> CheckRole
    CheckRole -- admin --> Admin
    CheckRole -- caixa/garcom --> NaoAdmin

    Admin --> AdminTudo["✅ tem TODAS as permissões<br/>(não bloqueável)"]

    NaoAdmin --> CheckCustom{permissoes_json<br/>preenchido?}
    CheckCustom -- sim --> UsaCustom["usa lista do JSON"]
    CheckCustom -- não --> UsaDefaults["usa DEFAULTS_POR_ROLE<br/>caixa = todos exceto perfil-admin<br/>garcom = caixa+entradas+novo_pedido"]

    UsaCustom --> Permissoes
    UsaDefaults --> Permissoes
    AdminTudo --> Permissoes

    subgraph Permissoes["Chaves de permissão (registry)"]
        K1[dashboard]
        K2[caixa]
        K3[relatorios]
        K4[produtos]
        K5[chopeiras]
        K6[entradas]
        K7[inventario]
        K8[novo_pedido]
    end

    Permissoes --> Decorator
    Decorator["@permissao_required('chave')<br/>em cada view"]
    Decorator --> Acesso{tem<br/>permissão?}
    Acesso -- sim --> ViewExecuta[view executa]
    Acesso -- não --> Erro403["abort(403)"]

    Permissoes --> Sidebar["Sidebar filtra<br/>itens via current_user.tem_permissao()"]
```

---

## 7. Mapa de rotas

```mermaid
graph LR
    subgraph Public["/auth + /public (sem permissão específica)"]
        R0["/  → index"]
        R1["/auth/login"]
        R2["/auth/logout"]
        R3["/auth/perfil — login_required"]
        R4["/public/novo"]
        R5["/public/mesas"]
        R6["/public/mesa/&lt;id&gt;"]
        R7["/public/retirada"]
        R8["/public/delivery"]
        R9["/public/pedido/&lt;id&gt;/cardapio"]
        R10["/public/pedido/&lt;id&gt;/editar"]
        R11["/public/pedido/&lt;id&gt;/enviado"]
        R12["/public/pedido/&lt;id&gt;/status"]
        R13["/public/pedidos — garçom"]
    end

    subgraph Admin["/admin (cada uma com @permissao_required)"]
        AD["dashboard → /admin/dashboard"]
        AC["caixa → /admin/pedidos<br/>+/cupom +/pagar +/fechar +/editar-caixa<br/>+/forcar-finalizacao +/cancelar"]
        AR["relatorios → /admin/relatorio/itens<br/>+/relatorio/bonificacao<br/>+/relatorio/exportar_csv*"]
        AP["produtos → /admin/produtos +/novo +/editar<br/>+/categorias/nova +/editar"]
        ACH["chopeiras → /admin/chopeiras +/&lt;id&gt;<br/>+/retornar +/detalhes +/relatorio<br/>+/relatorio/exportar-excel"]
        AE["entradas → /admin/entradas/produtos"]
        AI["inventario → /admin/inventario +/contar<br/>+/item/&lt;id&gt; +/produto/&lt;id&gt;<br/>+/relatorio +/relatorio/excel"]
    end

    subgraph AdminOnly["/admin (role admin only)"]
        AU["/admin/usuarios +/novo +/editar"]
        ACFG["/admin/config/pix"]
        AMM["/admin/mesa/&lt;id&gt;/liberar"]
    end

    subgraph Static["estáticos (servir arquivos)"]
        SU1["/uploads/produtos/&lt;file&gt;"]
        SU2["/uploads/usuarios/&lt;file&gt;"]
        SS["/static/&lt;path&gt;"]
    end
```

---

## 8. Fluxo de pedido

```mermaid
flowchart TB
    Inicio([Garçom abre app])
    Inicio --> Novo["/public/novo<br/>escolhe tipo"]

    Novo --> EscolheTipo{tipo?}
    EscolheTipo -- mesa --> Mesa["/public/mesas → seleciona mesa"]
    EscolheTipo -- retirada --> Retirada["/public/retirada<br/>(form cliente)"]
    EscolheTipo -- delivery --> Delivery["/public/delivery<br/>(form cliente+endereço)"]

    Mesa --> CriaPedido["cria Pedido vazio<br/>tipo=mesa, mesa.status=ocupada"]
    Retirada --> CriaPedido2["cria Pedido<br/>tipo=retirada"]
    Delivery --> CriaPedido3["cria Pedido<br/>tipo=delivery"]

    CriaPedido --> Cardapio["/public/pedido/&lt;id&gt;/cardapio<br/>seleciona produtos+qtd"]
    CriaPedido2 --> Cardapio
    CriaPedido3 --> Cardapio

    Cardapio --> Itens["adiciona PedidoItem<br/>(produto + quantidade)"]
    Itens --> Enviado["/public/pedido/&lt;id&gt;/enviado<br/>SocketIO emite 'novo_pedido'"]

    Enviado --> Caixa["Caixa recebe em tempo real<br/>/admin/pedidos"]

    Caixa --> AcoesCx{ação no caixa?}
    AcoesCx -- editar --> EditarCx["/admin/pedido/&lt;id&gt;/editar-caixa<br/>(adicionar/remover produto)"]
    AcoesCx -- pagar --> Pagar["/admin/pedido/&lt;id&gt;/pagar<br/>POST forma_pagamento"]
    AcoesCx -- cancelar (retirada/delivery) --> Cancelar["/admin/pedido/&lt;id&gt;/cancelar<br/>forma_pagamento='cancelado'"]
    AcoesCx -- forçar finalização (admin) --> Forcar["/admin/pedido/&lt;id&gt;/forcar-finalizacao<br/>forma_pagamento='cancelado'"]

    Pagar --> Cupom["/admin/pedido/&lt;id&gt;/cupom<br/>+ Pix QR se forma=pix"]
    Cupom --> Fechar["/admin/pedido/&lt;id&gt;/fechar<br/>POST → mesa=livre"]

    Fechar --> Final([Pedido finalizado<br/>entra em relatórios pela criado_em])
```

---

## 9. Estados do pedido

```mermaid
stateDiagram-v2
    [*] --> Recebido: criado
    Recebido --> Aberto: primeiro item adicionado
    Aberto --> Aberto: editar (add/remover/qtd)
    Aberto --> Finalizado: pagar+fechar (forma normal)
    Aberto --> Finalizado_Cancelado: cancelar (retirada/delivery)<br/>OU forçar finalização (admin)
    Aberto --> Finalizado_Cancelado: liberar mesa (admin)<br/>se pedido sem forma de pagamento

    Finalizado --> [*]
    Finalizado_Cancelado --> [*]

    note right of Finalizado
        forma_pagamento != 'cancelado'
        Conta nos RELATÓRIOS
        no dia da criação
    end note

    note right of Finalizado_Cancelado
        forma_pagamento = 'cancelado'
        NÃO aparece em relatórios
        Mesa liberada automaticamente
    end note
```

---

## 10. Estados da mesa e da chopeira

```mermaid
stateDiagram-v2
    state "MESA" as Mesa {
        [*] --> Livre
        Livre --> Ocupada: pedido aberto
        Ocupada --> Livre: pedido fechado<br/>OU admin libera mesa
    }

    state "CHOPEIRA" as Chop {
        [*] --> Disponivel
        Disponivel --> Alugada: registrar aluguel<br/>(cliente + equipamentos)
        Alugada --> Disponivel: confirmar devolução
    }
```

---

## 11. Aluguel de chopeiras

```mermaid
flowchart TB
    Lista["/admin/chopeiras<br/>grid das 76 chopeiras"]
    Filtros["Chips: Todas/Disponíveis/Alugadas<br/>Acordeão por tipo"]
    Lista --> Filtros

    Filtros --> Card{clica num<br/>card?}
    Card -- chopeira disponível --> AlugarFx["/admin/chopeiras/&lt;id&gt;<br/>(form aluguel)"]
    Card -- chopeira alugada --> Detalhes["/admin/chopeiras/&lt;id&gt;/detalhes"]

    AlugarFx --> AluguelDados["cliente_nome, telefone, endereço<br/>+ keg_tipo (P/G)<br/>+ checkboxes: CO2, manômetro, pingadeira"]
    AluguelDados --> SaveAluguel["AluguelChopeira(status='alugado')<br/>+ chopeira.status='alugada'"]

    Detalhes --> Devolver{botão<br/>'Devolver'?}
    Devolver -- sim --> ConfirmModal["modal confirmação"]
    ConfirmModal --> POSTRet["POST /admin/chopeiras/&lt;id&gt;/retornar"]
    POSTRet --> SaveDevolv["aluguel.status='devolvido'<br/>aluguel.data_retorno=now<br/>chopeira.status='disponivel'"]

    Lista --> Relatorio["/admin/chopeiras/relatorio<br/>todas alugadas atualmente"]
    Relatorio --> Excel["/admin/chopeiras/relatorio/exportar-excel"]
```

---

## 12. Pagamento e geração do cupom

```mermaid
flowchart TB
    Form["form de pagamento<br/>no card do caixa"]
    Form --> Forma{forma_pagamento}

    Forma -- dinheiro --> Dinheiro["valor_entregue + troco"]
    Forma -- pix --> Pix["valor_entregue=NULL"]
    Forma -- cartao --> Cartao["tipo_cartao (credito/debito)"]
    Forma -- bonif --> Bonif["valor_entregue=0<br/>(NÃO entra em relatório vendas)"]

    Dinheiro --> Submit
    Pix --> Submit
    Cartao --> Submit
    Bonif --> Submit
    Submit["POST /admin/pedido/&lt;id&gt;/pagar"]

    Submit --> CupomView["/admin/pedido/&lt;id&gt;/cupom"]

    CupomView --> CheckPix{pix?}
    CheckPix -- não --> CupomBasico["renderiza cupom branco<br/>com itens e total"]
    CheckPix -- sim --> GenPix["gerar_brcode(<br/>chave, nome, cidade,<br/>valor=total_com_desconto,<br/>txid=PED&lt;id&gt;)"]

    GenPix --> BRCode["payload EMV/BR Code<br/>com CRC16"]
    BRCode --> QR["gerar_qrcode_base64()<br/>PNG inline data:image"]
    QR --> CupomBasico

    CupomBasico --> Imprimir{user clica<br/>imprimir?}
    Imprimir -- sim --> Print["window.print()<br/>CSS @media print<br/>oculta sidebar/topbar"]
```

**Configuração da chave Pix** ([app/admin/configuracao.py](app/admin/configuracao.py)):

```mermaid
flowchart LR
    Admin[Admin abre /admin/config/pix]
    Admin --> Form[form: chave, nome, cidade]
    Form --> Submit[POST]
    Submit --> SaveJson["grava pix_settings.json<br/>ao lado do .exe"]
    SaveJson --> RuntimeUpdate["current_app.config[PIX_*] = ..."]
    RuntimeUpdate --> Done["próximo cupom já usa nova chave<br/>SEM reiniciar"]

    Boot[Boot do app]
    Boot --> CheckJson{pix_settings.json<br/>existe?}
    CheckJson -- sim --> LoadJson["carrega para app.config<br/>(sobrescreve config.py)"]
    CheckJson -- não --> UseDefault["usa default do config.py"]
```

---

## 13. Inventário (contagem diária)

```mermaid
flowchart TB
    Lista["/admin/inventario<br/>lista UNIFICADA<br/>operacionais + produtos"]
    Lista --> KPIs["KPIs:<br/>- Itens cadastrados<br/>- Contados hoje<br/>- Pendentes<br/>- Em alerta"]
    Lista --> Chips["Filtro chips:<br/>Todos / Operacionais / Cardápio"]

    Lista --> Acoes{ação?}
    Acoes -- + Novo item --> Novo["/admin/inventario/novo<br/>(só operacionais)"]
    Acoes -- ⚡ Itens padrão --> Seed["POST /admin/inventario/seed-padrao<br/>cria 6 itens (barril, kegs, CO2, etc.)"]
    Acoes -- 📋 Realizar contagem --> Contar["/admin/inventario/contar"]
    Acoes -- 📊 Relatório --> Relatorio["/admin/inventario/relatorio"]
    Acoes -- clica num card --> Detalhes

    Contar --> FormGeral["form com 2 seções:<br/>1) Itens operacionais<br/>2) Produtos do cardápio"]
    FormGeral --> ContagemSubmit["POST<br/>cada item preenchido vira<br/>ContagemInventario(item_id OR produto_id)"]
    ContagemSubmit --> CacheUpdate["atualiza ultima_quantidade<br/>e ultima_contagem_data"]

    Detalhes{tipo}
    Detalhes -- operacional --> ItemDetail["/admin/inventario/item/&lt;id&gt;"]
    Detalhes -- produto --> ProdDetail["/admin/inventario/produto/&lt;id&gt;"]
    ItemDetail --> Hist["histórico cronológico<br/>delta entre contagens"]
    ProdDetail --> Hist
    ItemDetail --> Rapida["lançar contagem rápida<br/>(1 item)"]
    ProdDetail --> Rapida

    Relatorio --> KPIRel["KPIs do período"]
    Relatorio --> Tabela["resumo por item:<br/>primeira/última qtd, variação"]
    Relatorio --> ExcelExport["⤓ Exportar Excel<br/>3 abas: Resumo / Por Item (pivot) / Detalhado"]

    Hist --> Excluir["admin pode excluir<br/>contagem errada<br/>→ recalcula cache"]
```

---

## 14. Relatórios e exportações

```mermaid
flowchart TB
    subgraph Vendas["📈 Relatório de itens vendidos"]
        VTela["/admin/relatorio/itens<br/>tela com KPIs+ranking"]
        VFiltros["chips rápidos:<br/>Hoje / 7d / 30d / Mês"]
        VExcel["⤓ /admin/relatorio/exportar_csv"]
        VTela --> VFiltros
        VTela --> VExcel
    end

    subgraph Bonif["🎁 Relatório de bonificação"]
        BTela["/admin/relatorio/bonificacao"]
        BExcel["⤓ /admin/relatorio/exportar_csv_bonif"]
        BTela --> BExcel
    end

    subgraph Inv["🗃️ Relatório de inventário"]
        ITela["/admin/inventario/relatorio"]
        IExcel["⤓ /admin/inventario/relatorio/excel<br/>3 abas Excel"]
        ITela --> IExcel
    end

    subgraph Chop["🍻 Chopeiras alugadas"]
        CTela["/admin/chopeiras/relatorio"]
        CExcel["⤓ /admin/chopeiras/relatorio/exportar-excel"]
        CTela --> CExcel
    end

    Filtro["Filtro de período:<br/>data_ini, data_fim"]
    Vendas --> Filtro
    Bonif --> Filtro

    Logica["Lógica do rateio de desconto:<br/>(subtotal_item / total_bruto_pedido) × desconto"]
    Vendas --> Logica
    Bonif -.usa.-> Logica
    note["Filtros excluem<br/>forma_pagamento IN ('bonif','cancelado')"]
    Vendas -.aplica.-> note
```

---

## 15. Migrações automáticas no boot

```mermaid
flowchart TB
    Boot([create_app inicia])
    Boot --> CreateAll["db.create_all()<br/>cria tabelas faltantes<br/>SEM tocar nas existentes"]

    CreateAll --> SecKey["_garantir_secret_key()<br/>gera .secret_key se default"]
    SecKey --> PixSet["_carregar_pix_settings()<br/>lê pix_settings.json se existir"]

    PixSet --> Backup{precisa<br/>migrar?}
    Backup -- sim --> CopiaDB["_backup_sqlite_pre_migracao()<br/>copia comanda.db para<br/>backups/comanda_pre_migracao_<TS>.db<br/>(mantém últimos 10)"]
    Backup -- não --> SkipBackup[skip backup]

    CopiaDB --> MigUsuarios
    SkipBackup --> MigUsuarios

    MigUsuarios["_migrar_coluna_permissoes()<br/>ALTER usuarios:<br/>+ permissoes_json TEXT<br/>+ foto VARCHAR"]
    MigUsuarios --> MigInv["_migrar_inventario_para_contagem()"]

    MigInv --> M1["DROP TABLE inventario_movimentos<br/>(legado, se existir)"]
    M1 --> M2["ALTER inventario_itens:<br/>+ ultima_quantidade<br/>+ ultima_contagem_data<br/>+ alerta_se_abaixo"]
    M2 --> M3["ALTER produtos:<br/>+ ultima_quantidade<br/>+ ultima_contagem_data<br/>+ alerta_se_abaixo"]
    M3 --> M4["DROP inventario_contagens<br/>se faltar produto_id"]

    M4 --> CreateAll2["db.create_all() de novo<br/>recria tabelas dropadas"]
    CreateAll2 --> Seed["seed_if_empty()<br/>cria mesas/chopeiras<br/>se vazias"]
    Seed --> Pronto([App pronto])

    note1["Todas migrações são IDEMPOTENTES<br/>e não-destrutivas para dados existentes"]
    MigInv -.-> note1
```

---

## 16. Persistência externa

```mermaid
graph TB
    subgraph PastaInst["Pasta de instalação (ao lado do .exe)"]
        Exe["DrinkGO.exe"]
        Internal["📁 _internal/<br/>(libs PyInstaller — descartável)"]
        DB[("comanda.db<br/>SQLite — banco de dados")]
        SK[".secret_key<br/>chave de sessão estável"]
        PJ["pix_settings.json<br/>chave Pix configurada via UI"]
        Cfg["config.py<br/>defaults (Pix, sessão)"]
        UpProd["📁 uploads/produtos/<br/>fotos cadastradas"]
        UpUser["📁 uploads/usuarios/<br/>fotos perfil"]
        Backups["📁 backups/<br/>cópias automáticas do .db<br/>antes de migrações"]
    end

    Sagrado["🔒 PRESERVAR ao atualizar:<br/>• comanda.db<br/>• .secret_key<br/>• pix_settings.json<br/>• uploads/<br/>• backups/<br/>• config.py (se editou)"]

    Descartavel["♻️ SUBSTITUI a cada update:<br/>• DrinkGO.exe<br/>• _internal/"]

    DB --> Sagrado
    SK --> Sagrado
    PJ --> Sagrado
    UpProd --> Sagrado
    UpUser --> Sagrado
    Backups --> Sagrado
    Cfg --> Sagrado

    Exe --> Descartavel
    Internal --> Descartavel
```

---

## 17. Build e deploy

```mermaid
flowchart LR
    subgraph Dev["Desenvolvimento"]
        Code["Código + templates + static"]
        Venv[".venv/ com deps<br/>(flask, socketio, pandas,<br/>qrcode, zeroconf, etc.)"]
        RunPy["python run.py<br/>(auto-reload, console)"]
    end

    Code --> Build
    Venv --> Build

    subgraph Build["Build PyInstaller"]
        Cmd["pyinstaller --onedir --noconsole<br/>--name DrinkGO<br/>--icon favicon.ico<br/>--hidden-import zeroconf, ifaddr,<br/>flask_socketio, PIL._tkinter_finder<br/>--collect-all socketio, zeroconf<br/>--add-data app, static, templates, config.py<br/>launcher.py"]
    end

    Build --> Artefato["dist/DrinkGO/<br/>├── DrinkGO.exe<br/>└── _internal/"]

    Artefato --> Deploy

    subgraph Deploy["Loja"]
        InstFolder["📁 ComandaDigital/"]
        InstFolder --> NovoExe["substitui .exe + _internal/"]
        InstFolder --> KeepFiles["mantém db, .secret_key,<br/>pix_settings.json, uploads/"]
        InstFolder --> Run["Usuária dá duplo-clique<br/>→ launcher.py inicia"]
    end

    Run --> Janela["🪟 Janela GUI<br/>(IP, mDNS, QR)"]
    Run --> Server["Flask + SocketIO :5020<br/>(thread daemon)"]
    Run --> MDNS["zeroconf registra<br/>comanda.local"]
```

---

## 18. Rede local

```mermaid
graph TB
    Maquina["💻 Máquina principal<br/>hostname: jabdev<br/>IP: 192.168.0.54"]

    Maquina --> Servidor["Servidor :5020"]
    Maquina --> Zeroconf["mDNS registra<br/>comanda.local"]

    subgraph Acesso["Como os tablets acessam"]
        Op1["★ http://comanda.local:5020<br/>FUNCIONA EM:<br/>iOS / Android 12+ / Win 10+ / Mac"]
        Op2["http://192.168.0.54:5020<br/>SEMPRE FUNCIONA<br/>(qualquer dispositivo IP)"]
        Op3["http://jabdev:5020<br/>SÓ outros PCs Windows<br/>(NetBIOS — tablets não fazem)"]
    end

    Servidor --> Op1
    Servidor --> Op2
    Servidor --> Op3

    Op1 --> Tablets["📱 Todos os tablets"]
    Op2 --> Tablets
    Op3 --> PCsWin["💻 PCs Windows"]

    QR["QR Code da janela GUI"]
    QR -. aponta para .-> Op2

    note1["⚠️ Tip: reservar IP fixo<br/>no DHCP do roteador<br/>(IP por MAC)"]
    Op2 -.-> note1
```

---

## 19. Sidebar e ícones

```mermaid
flowchart TB
    Sidebar[Sidebar — montada via Jinja em base.html]

    Sidebar --> CheckPerm{has perm?}
    CheckPerm --> P1["📊 Dashboard — has dashboard"]
    CheckPerm --> G1["▾ Vendas — has caixa OR novo_pedido"]
    CheckPerm --> G2["▾ Relatórios — has relatorios"]
    CheckPerm --> P2["📦 Produtos — has produtos"]
    CheckPerm --> G3["▾ Estoque — has entradas OR inventario OR chopeiras"]
    CheckPerm --> G4["▾ Admin — role == admin"]

    G1 --> SI1["➕ Novo Pedido"]
    G1 --> SI2["📋 Meus Pedidos (só garcom)"]
    G1 --> SI3["🧾 Caixa"]

    G2 --> SI4["🍺 Itens vendidos"]
    G2 --> SI5["🎁 Bonificação"]

    G3 --> SI6["📥 Entrada de Produtos"]
    G3 --> SI7["🗃️ Inventário"]
    G3 --> SI8["🍻 Aluguel de Chopeiras"]

    G4 --> SI9["👥 Usuários"]
    G4 --> SI10["⚡ Chave Pix"]

    Topbar["Topbar — sempre visível"]
    Topbar --> User["👤 Avatar + nome<br/>(dropdown details)"]
    User --> UD1["✏️ Editar Perfil → /auth/perfil"]
    User --> UD2["🚪 Sair → /auth/logout"]

    note["Ícones: SVG line-style<br/>(macros em _icons.html)<br/>currentColor + transitions"]
    Sidebar -.-> note
```

---

## Apêndice — fluxos transversais importantes

### A. Backup automático antes de migração

```mermaid
sequenceDiagram
    participant App
    participant Detector as _precisa_migrar()
    participant Disk as Disco
    participant Migra as Migrações

    App->>Detector: tem ALTER pendente?
    Detector->>Disk: inspect schema atual
    Detector-->>App: True/False
    alt True
        App->>Disk: shutil.copy2(comanda.db, backups/comanda_pre_migracao_<TS>.db)
        Disk-->>App: backup criado
        App->>Disk: rotaciona — mantém últimos 10
        App->>Migra: aplica ALTERs
    else False
        Note over App: nada a fazer
    end
```

### B. Permissão check com role admin sempre passa

```mermaid
flowchart LR
    Req[Request entra]
    Req --> Dec[@permissao_required key]
    Dec --> CheckLogin{logged in?}
    CheckLogin -- não --> Login[redirect /auth/login]
    CheckLogin -- sim --> CheckAdmin{role admin?}
    CheckAdmin -- sim --> Pass[passa direto]
    CheckAdmin -- não --> CheckPerm{tem permissão<br/>'key'?}
    CheckPerm -- sim --> Pass
    CheckPerm -- não --> Forbid[abort 403]
```

### C. Geração do payload Pix (BR Code)

```mermaid
flowchart TB
    Input[chave + nome + cidade + valor + txid]
    Input --> San["sanitiza:<br/>nome ASCII upper 25 chars<br/>cidade ASCII upper 15 chars"]
    San --> TLV["monta TLV EMV:<br/>00=Format Indicator<br/>01=Static<br/>26=MAI (br.gov.bcb.pix + chave)<br/>52=MCC<br/>53=BRL<br/>54=valor<br/>58=BR<br/>59=nome<br/>60=cidade<br/>62=TXID"]
    TLV --> Hash["CRC16-CCITT (XMODEM)<br/>do payload + '6304'"]
    Hash --> Final["payload completo<br/>+ '6304' + CRC4"]
    Final --> QRGen["qrcode.QRCode<br/>error_correction=M<br/>box_size=8"]
    QRGen --> PNG["PNG → BytesIO<br/>→ base64<br/>→ data:image/png;base64,..."]
```
