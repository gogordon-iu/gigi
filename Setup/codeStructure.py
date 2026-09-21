# Open up
# Have a face --> the screen is working
# Say something --> the speaker is working
# Ask to speak their name --> The microphone is working
# Look at their face and acknowledge --> the camera is working
# Have a short conversation --> LLM is working
# Calibrate the motors using the LLM
#


# Character
# - Face
# - Speech
# - Motion

# On every reboot
#  Greetings (if sees and recognize a face, personal greetings)
#  if not connected to a wifi, ask if wants to connect to a wifi
#  if not, ask if wants to be asked again on later reboots, or stop bothering it
#  if yes, check if there is a new git version, and ask if want to update

# Motor calibration
# Hi, let's calibrate my motors, together OK?
# I am going got move one motor at a time and ask you which joint it is
# It can be either my neck which moves my head
# It can be my torso
# It can be my left or right shoulders
# It can be my left or right elbows

#let's try
#-- move one motor to general center
# Did something move, say yes or no
# -- if no, change to another angle
# -- if yes
# which joint
# try from the list
# -- if not understood
# -- Go over and ask for yes or no
# *Calibrate this motor
# Excellent. Now, I will move my motor and you tell me which direction it is moving
# Increase angle
# Was it (left/right) / (up/down), based on the motor
# -- if left 
#     Show image
#     My motor should look like this. Say either More to move a little more or Stop when it reached that angle.
# -- if more
#    move 10 on angle
# -- if stop
#    Go to center, do the same for the other direction
#--- go to the next motor

# Great, now we mapped the different channels to specific motoros
# Now we need to find the boundaries of each motor.
# I'll go one motor at a time, start with the smallest angle and increase it, until you tell me it arrived at the maximum angle
# For each motor, I will show you how it should look like
# Let's start