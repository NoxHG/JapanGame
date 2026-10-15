#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nome do Script: main.py
Descrição: núcleo do jogo, aqui é o "EXE" principal do jogo feito em pygame.
Autor: Luiz Heytor do Nascimento
Data: 2026-10-06
Versão: 1.0
"""

# BIBLIOTECAS
import pygame
import sys
import time

# VARIÁVEIS

LARGURA = 800
ALTURA = 600
RUNNING = True
clock = pygame.time.Clock()
     
pygame.init()

pygame.display.set_caption("JapanGame")
screen = pygame.display.set_mode((LARGURA, ALTURA))

# MAIN

x = 100
y = 100
direction = 0

speed = 150
energia = 300
vida = 100

energia_max = 600
vida_max = 300
custo_dash = 45
dash_distancia = 100

municao = 5
cooldown_tiro = 0

consumo_energia = 150
while RUNNING:
     dt = clock.tick(60) / 1000
     
     for event in pygame.event.get():
        if event.type == pygame.QUIT:
            RUNNING = False
            pygame.quit()
            sys.exit()

     screen.fill((0, 0, 0))
# Personagens e objetos
     pygame.draw.circle(
         screen,
         (200, 200, 200),
         (x, y),
         10
    )
    
# UI
     largura_barra = 200
     altura_barra = 20

     proporcao = max(0, energia) / energia_max
     largura_atual = int(largura_barra * proporcao)

     # Fundo da barra
     pygame.draw.rect(
     screen,
     (60, 60, 60),
     (300, 500, largura_barra, altura_barra)
     )

     # Energia atual
     pygame.draw.rect(
     screen,
     (0, 100, 255),
     (300, 500, largura_atual, altura_barra)
     )
     
    
 # MOVIMENTAÇÃO DO PERSONAGEM
     keys = pygame.key.get_pressed()
     if keys[pygame.K_a]:
         x -= speed * dt
         direction = 1
     if keys[pygame.K_d]:
         x += speed * dt
         direction = 2
     if keys[pygame.K_w]:
         y -= speed * dt
         direction = 3
     if keys[pygame.K_s]:
         y += speed * dt
         direction = 4
     if keys[pygame.K_w] and keys[pygame.K_a]:
         direction = 5
     if keys[pygame.K_w] and keys[pygame.K_d]:
         direction = 6
     if keys[pygame.K_s] and keys[pygame.K_a]:
         direction = 7
     if keys[pygame.K_s] and keys[pygame.K_d]:
         direction = 8
     
     if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SPACE and energia >= custo_dash:
            if direction == 1:
                x -= dash_distancia
            elif direction == 2:
                x += dash_distancia
            elif direction == 3:
                y -= dash_distancia
            elif direction == 4:
                y += dash_distancia
            elif direction == 5:
                x -= dash_distancia * 0.7071
                y -= dash_distancia * 0.7071
            elif direction == 6:
                x += dash_distancia * 0.7071
                y -= dash_distancia * 0.7071
            elif direction == 7:
                x -= dash_distancia * 0.7071
                y += dash_distancia * 0.7071
            elif direction == 8:
                x += dash_distancia * 0.7071
                y += dash_distancia * 0.7071

            if direction != 0:
                energia -= custo_dash

     pygame.display.flip()
    