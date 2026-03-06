
# References

## TMF -- Service Layer (Tabela Consolidada)
========================================

| Domínio | Componente ODA | Open API TMF | Entidades SID principais | Descrição |
| --- | --- | --- | --- | --- |
| Service Design | Service Catalog Management | TMF633 | ServiceSpecification, ServiceSpecCharacteristic, ServiceLevelSpecification | Gestão do catálogo de serviços e respetivas especificações |
| Service Design | Product Catalog (dependência) | TMF620 | ProductSpecification, ProductOffering | Catálogo de produtos que referenciam serviços |
| Service Design | Resource Catalog (dependência) | TMF634 | ResourceSpecification | Catálogo de recursos que suportam serviços |
| Pre-Sales | Service Qualification | TMF645 | ServiceQualification | Verifica se um serviço pode ser fornecido numa localização |
| Order Management | Service Order Management | TMF641 | ServiceOrder, ServiceOrderItem | Gestão do ciclo de vida das ordens de serviço |
| Order Management | Product Order Management (relacionado) | TMF622 | ProductOrder | Pedido comercial que origina service orders |
| Inventory | Service Inventory | TMF638 | Service, ServiceRelationship, SupportingResource | Inventário de instâncias de serviços ativos |
| Inventory | Resource Inventory (dependência) | TMF639 | Resource | Inventário de recursos que suportam serviços |
| Provisioning | Service Activation & Configuration | TMF640 | ServiceConfiguration, Service | Ativação e configuração de serviços |
| Assurance | Alarm Management | TMF642 | Alarm | Gestão de alarmes relacionados com serviços |
| Assurance | Performance Management | TMF628 | PerformanceIndicator, PerformanceMeasurement | Monitorização de métricas e performance |
| Assurance | Service Test Management | TMF653 | ServiceTest, TestSpecification, TestResult | Testes de diagnóstico e validação de serviços |
| Assurance | Trouble Ticket Management | TMF621 | TroubleTicket | Gestão de incidentes e problemas reportados |
| Lifecycle Support | Appointment Management | TMF646 | Appointment | Gestão de agendamentos para instalação ou manutenção |
| Commercial Support | Quote Management | TMF648 | Quote | Gestão de cotações de serviços |
| Commercial Support | Agreement Management | TMF651 | Agreement, ServiceLevelAgreement | Gestão de contratos e SLA |


## Entidades SID mais importantes no Service Domain
================================================

| Entidade SID | Descrição |
| --- | --- |
| ServiceSpecification | Definição técnica e funcional de um serviço |
| Service | Instância ativa de um serviço |
| ServiceOrder | Pedido de criação/modificação de serviço |
| ServiceCharacteristic | Parâmetros configuráveis de um serviço |
| ServiceLevelSpecification | Definição de SLA |
| ServiceRelationship | Relação entre serviços (ex: CFS → RFS) |
| ServiceTest | Teste aplicado a um serviço |
| ServiceProblem | Problema identificado num serviço |


## Relação CFS / RFS no SID
========================

| Tipo de Serviço | Descrição |
| --- | --- |
| CFS (Customer Facing Service) | Serviço visível ao cliente (ex: Internet, VPN, IPTV) |
| RFS (Resource Facing Service) | Serviço técnico que suporta o CFS (ex: VLAN, MPLS, Access circuit) |


## Fluxo típico no Service Layer (TMF APIs)
========================================

| Etapa | API TMF |
| --- | --- |
| Design do serviço | TMF633 |
| Qualificação do serviço | TMF645 |
| Pedido comercial | TMF622 |
| Pedido técnico de serviço | TMF641 |
| Provisionamento | TMF640 |
| Inventário | TMF638 |
| Monitorização | TMF628 |
| Alarmes | TMF642 |
| Testes | TMF653 |
| Incidentes | TMF621 |



# TM Forum -- Service Layer (ODA / Frameworx)
==========================================

## Tabela Consolidada
==========================================

| Domínio | Componente ODA | Open API TMF | Entidades SID principais | Descrição |
| --- | --- | --- | --- | --- |
| Service Design | Service Catalog Management | TMF633 | ServiceSpecification, ServiceSpecCharacteristic, ServiceLevelSpecification | Gestão do catálogo de serviços e respetivas especificações |
| Service Design | Product Catalog (dependência) | TMF620 | ProductSpecification, ProductOffering | Catálogo de produtos que referenciam serviços |
| Service Design | Resource Catalog (dependência) | TMF634 | ResourceSpecification | Catálogo de recursos que suportam serviços |
| Pre-Sales | Service Qualification | TMF645 | ServiceQualification | Verifica se um serviço pode ser fornecido numa localização |
| Order Management | Service Order Management | TMF641 | ServiceOrder, ServiceOrderItem | Gestão do ciclo de vida das ordens de serviço |
| Order Management | Product Order Management (relacionado) | TMF622 | ProductOrder | Pedido comercial que origina service orders |
| Inventory | Service Inventory | TMF638 | Service, ServiceRelationship, SupportingResource | Inventário de instâncias de serviços ativos |
| Inventory | Resource Inventory (dependência) | TMF639 | Resource | Inventário de recursos que suportam serviços |
| Provisioning | Service Activation & Configuration | TMF640 | ServiceConfiguration, Service | Ativação e configuração de serviços |
| Assurance | Alarm Management | TMF642 | Alarm | Gestão de alarmes relacionados com serviços |
| Assurance | Performance Management | TMF628 | PerformanceIndicator, PerformanceMeasurement | Monitorização de métricas e performance |
| Assurance | Service Test Management | TMF653 | ServiceTest, TestSpecification, TestResult | Testes de diagnóstico e validação de serviços |
| Assurance | Trouble Ticket Management | TMF621 | TroubleTicket | Gestão de incidentes e problemas reportados |
| Lifecycle Support | Appointment Management | TMF646 | Appointment | Gestão de agendamentos para instalação ou manutenção |
| Commercial Support | Quote Management | TMF648 | Quote | Gestão de cotações de serviços |
| Commercial Support | Agreement Management | TMF651 | Agreement, ServiceLevelAgreement | Gestão de contratos e SLA |



## Entidades SID mais importantes no Service Domain
================================================

| Entidade SID | Descrição |
| --- | --- |
| ServiceSpecification | Definição técnica e funcional de um serviço |
| Service | Instância ativa de um serviço |
| ServiceOrder | Pedido de criação ou modificação de serviço |
| ServiceCharacteristic | Parâmetros configuráveis de um serviço |
| ServiceLevelSpecification | Definição de SLA |
| ServiceRelationship | Relação entre serviços (ex: CFS → RFS) |
| ServiceTest | Teste aplicado a um serviço |
| ServiceProblem | Problema identificado num serviço |


## Service Layer
==========================================

| TMF API | Nome | Função |
|---|---|---|
| TMF633 | Service Catalog Management | Catálogo de serviços |
| TMF638 | Service Inventory Management | Inventário de serviços |
| TMF641 | Service Order Management | Gestão de pedidos de serviço |
| TMF640 | Service Activation & Configuration | Ativação e configuração de serviços |
| TMF645 | Service Qualification | Verificação de disponibilidade |
| TMF653 | Service Test Management | Testes de serviço |
| TMF656 | Service Problem Management | Gestão de problemas de serviço |
| TMF657 | Service Quality Management | Qualidade de serviço |



## TM Forum -- Service Layer: ODA → APIs → SID
==========================================

| ODA Component | TMF Open API | SID Entity | Função |
| --- | --- | --- | --- |
| Service Catalog Management | TMF633 | ServiceSpecification, ServiceSpecCharacteristic, ServiceLevelSpecification | Criação, manutenção e consulta de especificações de serviço |
| Service Catalog Management | TMF620 | ProductSpecification, ProductOffering | Catálogo de produtos relacionados a serviços |
| Resource Catalog Management | TMF634 | ResourceSpecification | Catálogo de recursos que suportam serviços |
| Service Order Management | TMF641 | ServiceOrder, ServiceOrderItem | Criação e gestão de ordens de serviço |
| Product Order Management | TMF622 | ProductOrder | Pedido comercial que inicia o fluxo de service order |
| Service Inventory | TMF638 | Service, ServiceRelationship, SupportingResource | Inventário de instâncias de serviços ativos e suas relações |
| Resource Inventory | TMF639 | Resource | Inventário de recursos que suportam serviços |
| Service Activation & Configuration | TMF640 | ServiceConfiguration, Service | Provisionamento e ativação de serviços |
| Service Qualification | TMF645 | ServiceQualification | Verificação da possibilidade de entregar o serviço (pré-venda) |
| Service Test Management | TMF653 | ServiceTest, TestSpecification, TestResult | Testes de serviço e validação de qualidade |
| Service Problem Management | TMF656 | ServiceProblem, AffectedService, RootCause | Gestão de problemas de serviço |
| Service Quality Management | TMF657 | ServiceLevelSpecification, KPI, SLA | Medição de qualidade e SLAs de serviço |
| Alarm Management | TMF642 | Alarm | Gestão de alarmes gerados pelos serviços |
| Performance Management | TMF628 | PerformanceIndicator, PerformanceMeasurement | Monitoramento de métricas de serviço |
| Trouble Ticket Management | TMF621 | TroubleTicket, AffectedService | Gestão de incidentes e tickets de serviço |
| Appointment Management | TMF646 | Appointment | Agendamento de instalação ou manutenção |
| Quote Management | TMF648 | Quote, QuoteItem | Gestão de cotações de serviços |
| Agreement Management | TMF651 | Agreement, ServiceLevelAgreement | Gestão de contratos e SLAs |
| Service Orchestration | TMF640 + TMF652 | Service, ResourceOrder | Coordenação end-to-end de serviços e recursos |
| Lifecycle Management | TMF641 + TMF640 + TMF638 | ServiceOrder, Service, ServiceConfiguration | Ciclo completo de criação, ativação e atualização de serviços |



## TM Forum -- Service Layer: SID Entities Mapeadas
===============================================

| SID Entity | ODA Component | TMF Open API | Função / Descrição |
| --- | --- | --- | --- |
| **ServiceSpecification** | Service Catalog Management | TMF633 | Definição técnica e funcional de um serviço; inclui características, SLAs e restrições |
| **ServiceSpecCharacteristic** | Service Catalog Management | TMF633 | Características configuráveis da especificação de serviço |
| **ServiceLevelSpecification** | Service Catalog / Quality Management | TMF633, TMF657 | SLA e métricas de nível de serviço |
| **ProductSpecification** | Product Catalog | TMF620 | Especificação de produto relacionado a um serviço |
| **ProductOffering** | Product Catalog | TMF620 | Oferta comercial do produto/serviço |
| **ResourceSpecification** | Resource Catalog | TMF634 | Definição de recursos necessários para suportar serviços |
| **ServiceOrder** | Service Order Management | TMF641 | Pedido de criação, modificação ou cancelamento de serviço |
| **ServiceOrderItem** | Service Order Management | TMF641 | Item individual de uma ordem de serviço |
| **ProductOrder** | Product Order Management | TMF622 | Pedido comercial que aciona a criação de ServiceOrders |
| **Service** | Service Inventory / Activation | TMF638, TMF640 | Instância ativa de um serviço (CFS) |
| **ServiceRelationship** | Service Inventory | TMF638 | Relação entre serviços (ex.: CFS → RFS) |
| **SupportingResource** | Service Inventory | TMF638 | Recurso de suporte ao serviço (RFS) |
| **Resource** | Resource Inventory | TMF639 | Recurso físico ou lógico suportando um serviço |
| **ServiceConfiguration** | Service Activation | TMF640 | Configurações aplicadas a uma instância de serviço |
| **ServiceQualification** | Pre-Sales / Qualification | TMF645 | Resultado de verificação de disponibilidade de serviço |
| **ServiceTest** | Service Test Management | TMF653 | Teste aplicado a um serviço |
| **TestSpecification** | Service Test Management | TMF653 | Especificação de teste |
| **TestResult** | Service Test Management | TMF653 | Resultado do teste aplicado ao serviço |
| **ServiceProblem** | Service Problem Management | TMF656 | Problema identificado em um serviço |
| **AffectedService** | Service Problem / Trouble Ticket | TMF621, TMF656 | Serviço afetado por um problema ou incidente |
| **RootCause** | Service Problem | TMF656 | Causa raiz de um problema |
| **Alarm** | Assurance / Alarm Management | TMF642 | Alarme gerado por falha ou evento no serviço |
| **PerformanceIndicator** | Performance Management | TMF628 | Métrica de desempenho de serviço |
| **PerformanceMeasurement** | Performance Management | TMF628 | Medição associada a um KPI ou indicador de serviço |
| **TroubleTicket** | Trouble Ticket Management | TMF621 | Ticket de incidente gerenciado |
| **Appointment** | Lifecycle Support | TMF646 | Agendamento de instalação, manutenção ou visita |
| **Quote** | Commercial Support | TMF648 | Cotações de serviços/produtos para cliente |
| **QuoteItem** | Commercial Support | TMF648 | Item individual dentro de uma cotação |
| **Agreement** | Commercial Support | TMF651 | Contrato ou acordo com o cliente |
| **ServiceLevelAgreement (SLA)** | Commercial Support / Quality | TMF651 | SLA acordado entre cliente e provedor |
| **ResourceOrder** | Orchestration / Resource Management | TMF652 | Ordem de provisionamento de recursos relacionados ao serviço |




## TM Forum -- ODA Master Mapping: ODA → Open API → SID
===================================================

| ODA Component / Layer | TMF Open API | SID Entity | Função / Descrição | Dependências / Observações |
| --- | --- | --- | --- | --- |
| Customer / Party Management | TMF629 | Customer | Gestão de clientes | Pode alimentar ProductOrder / ServiceOrder |
| Customer / Party Management | TMF632 | Party | Gestão de pessoas ou organizações | Cross-layer com ProductOffering e ServiceOrder |
| Customer / Party Management | TMF669 | PartyRole | Gestão de papéis de parties | Associado a Customer e ProductOrder |
| Customer / Party Management | TMF672 | UserRolePermission | Permissões e roles | Relevante para sistemas BSS e portais |
| Customer / Party Management | TMF683 | PartyInteraction | Registro de interações com clientes | Integra com ServiceOrder / TroubleTicket |
| Product Layer | TMF620 | ProductSpecification, ProductOffering | Catálogo de produtos | Pode gerar ProductOrder |
| Product Layer | TMF622 | ProductOrder | Pedido comercial | Gera ServiceOrder no Service Layer |
| Product Layer | TMF648 | Quote, QuoteItem | Cotações de serviços/produtos | Pré-venda; gera ProductOrder |
| Product Layer | TMF671 | Promotion | Gestão de promoções | Associado a ProductOffering |
| Product Layer | TMF679 | ProductOfferingQualification | Verificação pré-venda | Cross-layer com ServiceQualification |
| Service Layer | TMF633 | ServiceSpecification, ServiceSpecCharacteristic, ServiceLevelSpecification | Definição de serviços | Base para ServiceOrder e ServiceActivation |
| Service Layer | TMF641 | ServiceOrder, ServiceOrderItem | Gestão do ciclo de vida de ordens de serviço | Recebe ProductOrder (TMF622) |
| Service Layer | TMF638 | Service, ServiceRelationship, SupportingResource | Inventário de serviços ativos | Atualizado por ServiceActivation (TMF640) |
| Service Layer | TMF640 | ServiceConfiguration, Service | Ativação e configuração de serviço | Gera instâncias no ServiceInventory (TMF638) |
| Service Layer | TMF645 | ServiceQualification | Verificação de entrega de serviço | Pré-venda; depende de ServiceSpecification |
| Service Layer | TMF653 | ServiceTest, TestSpecification, TestResult | Testes de serviço | Pode gerar TroubleTicket se falha |
| Service Layer | TMF656 | ServiceProblem, AffectedService, RootCause | Gestão de problemas de serviço | Integra com TroubleTicket (TMF621) |
| Service Layer | TMF657 | ServiceLevelSpecification, KPI, SLA | Qualidade de serviço | Medições associadas a Service e Customer |
| Service Layer | TMF642 | Alarm | Gestão de alarmes | Alimenta TroubleTicket (TMF621) |
| Service Layer | TMF628 | PerformanceIndicator, PerformanceMeasurement | Monitoramento de performance | Pode ser reportado a Customer / Product dashboards |
| Service Layer | TMF621 | TroubleTicket, AffectedService | Gestão de incidentes | Recebe alertas de Alarm e ServiceTest |
| Service Layer | TMF646 | Appointment | Agendamentos de instalação/manutenção | Cross-layer: Resource / Service |
| Service Layer | TMF651 | Agreement, ServiceLevelAgreement | Contratos e SLAs | Associado a Customer, Service e Product |
| Resource / Network Layer | TMF634 | ResourceSpecification | Catálogo de recursos | Suporte a ServiceSpecification |
| Resource / Network Layer | TMF639 | Resource | Inventário de recursos | Suporte a Service / CFS-RFS |
| Resource / Network Layer | TMF652 | ResourceOrder | Pedido de provisionamento de recursos | Gera Resource / SupportingResource |
| Resource / Network Layer | TMF664 | ResourceFunctionActivation | Provisionamento de funções de rede | Depende de ResourceOrder |
| Resource / Network Layer | TMF716 | ResourceReservation | Reserva de recursos | Integra com ServiceActivation |
| Billing / Revenue Layer | TMF654 | PrepayBalance | Gestão de saldo pré-pago | Pode afetar ServiceOrder / ProductOrder |
| Billing / Revenue Layer | TMF666 | Account | Contas de clientes | Integra com ProductOrder / ServiceOrder |
| Billing / Revenue Layer | TMF676 | Payment | Gestão de pagamentos | Cross-layer: Product / Service |
| Billing / Revenue Layer | TMF677 | UsageConsumption | Consumo de serviços | Coleta dados de Service / Resource |
| Billing / Revenue Layer | TMF678 | CustomerBill | Faturação | Consolidado de ProductOrder + ServiceUsage |
| Billing / Revenue Layer | TMF735 | CDRTransaction | Registros de chamadas | Integra com UsageConsumption |
| Billing / Revenue Layer | TMF737 | RevenueSharingReport | Relatórios de revenue sharing | Cross-layer com Billing e Service |
| Billing / Revenue Layer | TMF738 | RevenueSharingModel | Modelos de revenue sharing | Depende de Service e Product |
| Geographic / Location Layer | TMF673 | GeographicAddress | Gestão de moradas | Relevante para ServiceQualification / ProductOrder |
| Geographic / Location Layer | TMF674 | GeographicSite | Gestão de sites | Integra com Resource / Service |
| Sales / Commerce | TMF699 | Sales | Gestão de vendas | Cross-layer: ProductOffering e Quote |
| Sales / Commerce | TMF680 | Recommendation | Recomendação de produtos | Baseado em Customer e Product |
| Inventory / Logistics | TMF687 | Stock | Gestão de stock físico | Integra com Product / Resource |
| Testing / DevOps | TMF704 | TestCase | Gestão de casos de teste | Apoia ServiceTest (TMF653) |
| Testing / DevOps | TMF705 | TestEnvironment | Gestão de ambientes de teste | Apoia ServiceActivation e ServiceTest |
| Testing / DevOps | TMF706 | TestData | Dados de teste | Apoia ServiceTest |
| Testing / DevOps | TMF707 | TestResult | Resultados de teste | Integra com ServiceTest e TroubleTicket |
| Testing / DevOps | TMF708 | TestExecution | Execução de testes | Apoia ServiceTest |
| Testing / DevOps | TMF709 | TestScenario | Cenário de teste | Apoia ServiceTest |
| Testing / DevOps | TMF710 | TestArtifact | Artefactos de teste | Apoia ServiceTest |
| Platform / Emerging | TMF915 | AIModel | Gestão de modelos de IA | Pode gerar recomendações ou otimizações de Service |
| Platform / Emerging | TMF921 | Intent | Automação baseada em intenções | Pode disparar ServiceOrder ou ResourceOrder |
| Platform / Emerging | TMF931 | OpenGatewayOnboarding | Onboarding / Order APIs | Permite integração de novos provedores ou clientes |


mermaid**

flowchart TD
ProductOrder[TMF622 ProductOrder] --> ServiceOrder[TMF641 ServiceOrder]
ServiceOrder --> Activation[TMF640 ServiceActivation]
Activation --> Inventory[TMF638 ServiceInventory]
Inventory --> Assurance[TMF642 / TMF628 / TMF653]
Assurance --> TroubleTicket[TMF621 TroubleTicket]

**

## Observações do Mapa Visual
==========================

1.  **Camadas**:

    -   **Customer / Party** → ProductOrder / ServiceOrder

    -   **Product Layer** → ProductCatalog, ProductOrder, Quote

    -   **Service Layer** → ServiceCatalog, ServiceOrder, ServiceInventory, Activation, Test, Problem, Quality

    -   **Resource Layer** → ResourceCatalog, ResourceInventory, ResourceOrder, ResourceActivation, Reservation

    -   **Assurance / Ops** → Alarm, Performance, TroubleTicket

    -   **Billing / Finance** → Account, Usage, CustomerBill

    -   **Platform / Emerging** → AI, Intent, OpenGateway

2.  **Fluxo end-to-end**:

    -   **ProductOrder → ServiceOrder → ServiceActivation → ServiceInventory → Assurance/Billing**

    -   **ServiceActivation → ResourceOrder → ResourceActivation → ResourceInventory → ServiceInventory**

3.  **Eventos TMF**:

    -   Cada API pode disparar **eventos SID** (ex.: `ServiceCreateEvent`, `ServiceStateChangeEvent`, `AlarmRaisedEvent`) para integração **event-driven**.

4.  **CFS vs RFS**:

    -   `Service` → Customer Facing Service (CFS)

    -   `SupportingResource` ou `Resource` → Resource Facing Service (RFS)

