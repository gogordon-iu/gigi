import pygame
import sys
import random
from pygame.locals import *

# Initialize Pygame
pygame.init()

# Screen setup
screen_width, screen_height = pygame.display.get_desktop_sizes()[0]
screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
pygame.display.set_caption("Robot Face")

# Colors
BACKGROUND_COLOR = (30, 30, 30)
EYE_COLOR = (255, 255, 255)
PUPIL_COLOR = (0, 0, 0)
MOUTH_COLOR = (200, 0, 0)
EYEBROW_COLOR = (100, 50, 0)
TEAR_COLOR = (0, 100, 255)

# Clock for animation
clock = pygame.time.Clock()

# Variables for blinking
blink_counter = 0
blink_duration = 0
is_blinking = False


def draw_face(mouth_shape="neutral", eye_position="center", eyebrow_angle="normal", tears=False, blinking=False):
    """
    Draws the robot's face with dynamic features.
    """
    screen.fill(BACKGROUND_COLOR)

    # Eye positions
    left_eye_x, left_eye_y = screen_width // 3, screen_height // 3
    right_eye_x, right_eye_y = 2 * screen_width // 3, screen_height // 3
    eye_width, eye_height = 240, 150
    pupil_radius = 40

    # Draw eyes
    if blinking:
        pygame.draw.rect(screen, EYE_COLOR, (left_eye_x - eye_width // 2, left_eye_y, eye_width, 20))
        pygame.draw.rect(screen, EYE_COLOR, (right_eye_x - eye_width // 2, right_eye_y, eye_width, 20))
    else:
        pygame.draw.ellipse(screen, EYE_COLOR, (left_eye_x - eye_width // 2, left_eye_y - eye_height // 2, eye_width, eye_height))
        pygame.draw.ellipse(screen, EYE_COLOR, (right_eye_x - eye_width // 2, right_eye_y - eye_height // 2, eye_width, eye_height))

        # Adjust pupil position for "eye_position"
        pupil_offset = 30 if eye_position == "left" else (-30 if eye_position == "right" else 0)
        pygame.draw.circle(screen, PUPIL_COLOR, (left_eye_x + pupil_offset, left_eye_y), pupil_radius)
        pygame.draw.circle(screen, PUPIL_COLOR, (right_eye_x + pupil_offset, right_eye_y), pupil_radius)

    # Draw eyebrows
    if eyebrow_angle == "angry":
        pygame.draw.polygon(screen, EYEBROW_COLOR, [(left_eye_x - 120, left_eye_y - 150), (left_eye_x + 50, left_eye_y - 140), (left_eye_x + 20, left_eye_y - 110)])
        pygame.draw.polygon(screen, EYEBROW_COLOR, [(right_eye_x - 50, right_eye_y - 140), (right_eye_x + 120, right_eye_y - 150), (right_eye_x + 80, right_eye_y - 110)])
    elif eyebrow_angle == "surprised":
        pygame.draw.arc(screen, EYEBROW_COLOR, (left_eye_x - 130, left_eye_y - 180, 150, 50), 3.14, 6.28, 10)
        pygame.draw.arc(screen, EYEBROW_COLOR, (right_eye_x - 20, right_eye_y - 180, 150, 50), 3.14, 6.28, 10)
    else:
        pygame.draw.line(screen, EYEBROW_COLOR, (left_eye_x - 120, left_eye_y - 150), (left_eye_x + 80, left_eye_y - 150), 10)
        pygame.draw.line(screen, EYEBROW_COLOR, (right_eye_x - 80, right_eye_y - 150), (right_eye_x + 120, right_eye_y - 150), 10)

    # Draw mouth
    mouth_width = screen_width // 4
    mouth_height = 60 if mouth_shape == "neutral" else (120 if mouth_shape == "happy" else -120)
    mouth_y = screen_height // 1.5

    if mouth_shape == "speaking":
        mouth_height = random.choice([30, 60, 90])

    if mouth_shape == "surprised":
        pygame.draw.ellipse(screen, MOUTH_COLOR, (screen_width // 2 - mouth_width // 2, mouth_y, mouth_width, 180))
    else:
        pygame.draw.arc(screen, MOUTH_COLOR, (screen_width // 2 - mouth_width // 2, mouth_y, mouth_width, 200),
                        0 if mouth_shape == "happy" else 3.14, 3.14 if mouth_shape == "happy" else 6.28, 10)

    # Draw tears
    if tears:
        pygame.draw.ellipse(screen, TEAR_COLOR, (left_eye_x - 40, left_eye_y + 100, 20, 50))
        pygame.draw.ellipse(screen, TEAR_COLOR, (right_eye_x - 40, right_eye_y + 100, 20, 50))


def blink():
    """
    Handles blinking by setting the blinking state for a short duration.
    """
    global is_blinking, blink_counter, blink_duration
    if not is_blinking and random.random() < 0.01:  # 1% chance to start blinking
        is_blinking = True
        blink_duration = random.randint(5, 10)  # Blink duration in frames
        blink_counter = 0
    elif is_blinking:
        blink_counter += 1
        if blink_counter >= blink_duration:
            is_blinking = False


def speak():
    """
    Simulates speaking by animating the mouth for a short duration.
    """
    for _ in range(20):  # Speaking animation lasts 20 frames
        draw_face(mouth_shape="speaking")
        pygame.display.flip()
        clock.tick(15)
    draw_face(mouth_shape="neutral")


# Main loop
def main():
    current_emotion = "neutral"
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_h:
                    current_emotion = "happy"
                elif event.key == K_s:
                    current_emotion = "sad"
                elif event.key == K_a:
                    current_emotion = "angry"
                elif event.key == K_u:
                    current_emotion = "surprised"
                elif event.key == K_SPACE:
                    speak()
                elif event.key == K_n:
                    current_emotion = "neutral"

        blink()  # Handle blinking
        draw_face(mouth_shape=current_emotion, blinking=is_blinking)
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
