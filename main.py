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
boost = False
velocidade_boost = 0

while RUNNING:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            RUNNING = False
            pygame.quit()
            sys.exit()

    pygame.draw.rect(
         screen,
         (200, 200, 200),
         (x, y, 50, 50)
    )

    keys = pygame.key.get_pressed()
    if keys[pygame.K_a]:
         x -= 1 * (velocidade_boost if boost == True else 1)
    if keys[pygame.K_d]:
         x += 1 * (velocidade_boost if boost == True else 1)
    if keys[pygame.K_w]:
         y -= 1 * (velocidade_boost if boost == True else 1)
    if keys[pygame.K_s]:
         y += 1 * (velocidade_boost if boost == True else 1)
    if keys [pygame.K_SPACE]:
         screen.fill((0, 0, 0))
    if keys[pygame.K_LSHIFT]:
         boost = True
    pygame.display.flip()
    clock.tick(60)
    