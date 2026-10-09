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

direction = 0
x = 100
y = 100
energia = 300

while RUNNING:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            RUNNING = False
            pygame.quit()
            sys.exit()

    screen.fill((0, 0, 0))
# Personagens e objetos
    pygame.draw.rect(
         screen,
         (200, 200, 200),
         (x, y, 50, 50)
    )
# UI
    pygame.draw.rect(
         screen,
         (120, 0, 110),
         (10, 10, energia, 40)
    )
     
    
 # MOVIMENTAÇÃO DO PERSONAGEM
    keys = pygame.key.get_pressed()
    if keys[pygame.K_a]:
         x -= 1
         direction = 1
    if keys[pygame.K_d]:
         x += 1
         direction = 2
    if keys[pygame.K_w]:
         y -= 1
         direction = 3
    if keys[pygame.K_s]:
         y += 1
         direction = 4
    if keys[pygame.K_w + pygame.K_a]:
         direction = 5
    if keys[pygame.K_w + pygame.K_d]:
         direction = 6
    if keys[pygame.K_s + pygame.K_a]:
         direction = 7
    if keys[pygame.K_s + pygame.K_d]:
         direction = 8
    if keys [pygame.K_SPACE]:
          if direction == 1 and energia > 0:
             x -= 10
             energia -= 2
          if direction == 2 and energia > 0:
             x += 10
             energia -= 2
          if direction == 3 and energia > 0:
             y -= 10
             energia -= 2
          if direction == 4 and energia > 0:
             y += 10
             energia -= 2
          if direction == 5 and energia > 0:
             x -= 20
             y -= 10
             energia -= 2
          if direction == 6 and energia > 0:
               x += 20
               y += 10
               energia -= 2
          if direction == 7 and energia > 0:
               x -= 20
               y += 10
               energia -= 2
          if direction == 8 and energia > 0:
               x += 20
               y -= 10
               energia -= 2

    pygame.display.flip()
    clock.tick(90)
    