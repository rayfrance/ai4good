# Evaluating CNN Architectures Using Attention Mechanisms: Convolutional Block Attention Module, Squeeze, and Excitation for Image Classification on CIFAR10 Dataset

**Autores:** Abhisek Ganguly, A. Usha Ruby, George Chellin Chandran J.  
**Publicado em:** ResearchGate Preprint / Computer Vision Research, Agosto de 2023.  
**DOI / Identificador:** DOI: 10.13140/RG.2.2.33649.66408  
**Link:** [ResearchGate Publication](https://www.researchgate.net/publication/373460838_Evaluating_CNN_Architectures_Using_Attention_Mechanisms_Convolutional_Block_Attention_Module_Squeeze_and_Excitation_for_Image_Classification_on_CIFAR10_Dataset)

---

## O que propõe

O artigo investiga o impacto de acoplar mecanismos de atenção leves em diversas arquiteturas convolucionais clássicas e modernas (como ResNet, Inception, ResNeXt e MobileNet) para a tarefa de classificação de imagens no benchmark **CIFAR-10**. Especificamente, avalia dois mecanismos fundamentais:
1. **Squeeze-and-Excitation (SE):** Focado em atenção de canais (interdependência entre filtros).
2. **Convolutional Block Attention Module (CBAM):** Combinação sequencial de atenção espacial e de canais.

## Métodos principais

- **Operação Squeeze:** Compressão espacial através de Global Average Pooling ($GAP$):
  $$z_c = \mathbf{F}_{sq}(\mathbf{u}_c) = \frac{1}{H \times W} \sum_{i=1}^H \sum_{j=1}^W u_c(i,j)$$
- **Operação Excitation:** Captura das relações não-lineares e não-mutuamente exclusivas entre canais via gargalo (bottleneck) com fator de redução $r$:
  $$s = \mathbf{F}_{ex}(z, \mathbf{W}) = \sigma(\mathbf{W}_2 \, \delta(\mathbf{W}_1 z))$$
  onde $\delta$ é a ativação ReLU, $\mathbf{W}_1 \in \mathbb{R}^{\frac{C}{r} \times C}$, $\mathbf{W}_2 \in \mathbb{R}^{C \times \frac{C}{r}}$ e $\sigma$ é a função Sigmoide.
- **Recalibração (Scale):**
  $$\tilde{\mathbf{x}}_c = \mathbf{F}_{scale}(\mathbf{u}_c, s_c) = s_c \cdot \mathbf{u}_c$$
- Protocolo de avaliação sistemático comparando convergência, perda (Loss), precisão e acurácia top-1 em dados de baixa resolução (32x32) com fundos ruidosos.

## Resultados relevantes

- A inclusão do mecanismo de atenção de canais (SE) confere um ganho consistente de acurácia com sobrecusto paramétrico insignificante (menos de 1% a 2% de parâmetros adicionais).
- A atenção permite que os filtros aprendam a suprimir canais que capturam artefatos ou fundo irrelevante e reforcem características estruturais essenciais dos objetos.

## Conexão com nosso trabalho (Entrega 2 - AI4Good)

- Adotamos a formulação do bloco **Squeeze-and-Excitation (SE)** proposta e avaliada no artigo de 2023 como a **modificação substancial de arquitetura** da nossa rede neural convolucional.
- Mantemos como benchmark primário o **CIFAR-10** (como no artigo) e estendemos a verificação para o desafio do professor em um segundo dataset (**Fashion-MNIST**), provando generalização entre domínios visuais distintos.

## Citação BibTeX

```bibtex
@article{ganguly2023evaluating,
  author    = {Abhisek Ganguly and A. Usha Ruby and George Chellin Chandran J.},
  title     = {Evaluating CNN Architectures Using Attention Mechanisms: Convolutional Block Attention Module, Squeeze, and Excitation for Image Classification on CIFAR10 Dataset},
  journal   = {Preprint},
  year      = {2023},
  month     = {August},
  doi       = {10.13140/RG.2.2.33649.66408}
}
```
