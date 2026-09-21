"""
Interactive motor calibration wizard for Gigi social robot.

Guides the user through identifying joint-to-channel assignments, determining
minimum/maximum angle boundaries, and saving the resulting motor calibration
directly to the robot-local, untracked motorData_calibrated.json.
"""

import os
import sys
import json
import logging
from typing import Optional, Any

from gigi.activities.scripted.engine import Script
from gigi.activities.scripted.script_graph import ScriptGraph
from gigi.core.robot import Character
from gigi.hardware.calibration import load_motor_calibration, save_motor_calibration
from gigi.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

activity_name = "Motor Calibration"


class MotorCalibration(ScriptGraph): 
    def __init__(self, movement=None):
        super().__init__()

        self.movement = movement
        if not self.movement:
            try:
                from gigi.expression.movement import Movement
                self.movement = Movement(allow_uncalibrated=True)
                self.data['motors'] = self.movement.motor_map
            except Exception as e:
                logger.warning(f"Could not initialize Movement with allow_uncalibrated: {e}")
                self.data['motors'] = load_motor_calibration()
        else:
            self.data['motors'] = getattr(self.movement, "motor_map", load_motor_calibration())

        self.motor_words = "[" + " ".join(["\"%s\"," % m.replace("_", " ") for m in self.data['motors']]) + "\"[unk]\"]"
        self.number_motors = len(self.data['motors']) + 1
        self.base_angle = 300

    def init_graph(self):
        # Add introductory dialogue
        self.graph.add_node("start", type="speak", text="Hi, let's calibrate my motors, together.")
        text = [
            "I am going to move one motor at a time and ask you which joint it is.",
            "It can be either my neck which moves my head.",
            "It can be my torso.",
            "It can be my left or right shoulders.",
            "It can be my left or right elbows.",
            "Let's try"
        ]
        for i, t in enumerate(text):
            self.graph.add_node("text_%d" % i, type="speak", text=t)
            if i > 0:
                self.graph.add_edge("text_%d" % (i-1), "text_%d" % i, label="text_link_%d_%d" % (i-1, i))

        self.graph.add_edge("start", "text_0", label="start speak")
        self.graph.add_edge("text_%d" % (len(text)-1), "channel_move_0", label="start speak")

        for channel_idx in range(16):
            # Move motor on channel and ask if user noticed movement
            self.graph.add_node("channel_move_%d" % channel_idx, type="move", 
                                motors={channel_idx: self.base_angle})

            self.graph.add_node("channel_ask_%d" % channel_idx, type="speak", text="Did something move, say yes or no.")
            self.graph.add_edge("channel_move_%d" % channel_idx, 
                                "channel_ask_%d" % channel_idx, 
                                label="move ask confirmation %d" % channel_idx)

            self.graph.add_node("confirmation_moved_%d" % channel_idx, type="hear", words='["yes", "no", "[unk]"]')
            self.graph.add_edge("channel_ask_%d" % channel_idx, 
                                "confirmation_moved_%d" % channel_idx, 
                                label="ask hear confirmation %d" % channel_idx)
            
            # If it did not move, advance to the next channel
            self.graph.add_node("channel_not_moved_%d" % channel_idx, type="speak", text="Trying again.")
            self.graph.add_edge("confirmation_moved_%d" % channel_idx, 
                                "channel_not_moved_%d" % channel_idx,
                                label="no")
            
            if channel_idx < 15:
                self.graph.add_edge("channel_not_moved_%d" % channel_idx,
                                    "channel_move_%d" % (channel_idx + 1),
                                    label="trying next one")
            else:
                self.graph.add_edge("channel_not_moved_%d" % channel_idx,
                                    "finished",
                                    label="tried last one")

            # If a motor moved, ask which joint
            self.graph.add_node("channel_moved_%d" % channel_idx, type="speak", text="which joint?")
            self.graph.add_edge("confirmation_moved_%d" % channel_idx, 
                                "channel_moved_%d" % channel_idx,
                                label="yes")
            
            self.graph.add_node("confirmation_joint_%d" % channel_idx, type="hear", words=self.motor_words)
            self.graph.add_edge("channel_moved_%d" % channel_idx,
                                "confirmation_joint_%d" % channel_idx,
                                label="what moved")
            
            # Calibrate the joint
            for w in self.data['motors'].keys():
                self.graph.add_node("start_calibrate_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Excellent. Now we will calibrate the %s motor." % w.replace("_", " "))
                self.graph.add_edge("confirmation_joint_%d" % channel_idx,
                                    "start_calibrate_%s_%d" % (w, channel_idx),
                                    label=w.replace("_", " "))
                
                # Calibrate maximum boundary
                self.graph.add_node("show_max_%s_%d" % (w, channel_idx), type="show", 
                                    image="%s_max.jpg" % w)
                self.graph.add_edge("start_calibrate_%s_%d" % (w, channel_idx),
                                    "show_max_%s_%d" % (w, channel_idx),
                                    label="show max %s" % w)
                
                self.graph.add_node("explain_max_%s_%d" % (w, channel_idx), type="speak", 
                                    text="I will move my motor until it reaches this position.")
                self.graph.add_edge("show_max_%s_%d" % (w, channel_idx),
                                    "explain_max_%s_%d" % (w, channel_idx),
                                    label="explain max %s" % w)
                
                self.graph.add_node("channel_change_max_%s_%d" % (w, channel_idx), type="change", 
                                    what="angle", by=10)
                self.graph.add_edge("explain_max_%s_%d" % (w, channel_idx),
                                    "channel_change_max_%s_%d" % (w, channel_idx),
                                    label="change max %s" % w)

                self.graph.add_node("channel_move_max_%s_%d" % (w, channel_idx), type="move", 
                                    motors={channel_idx: self.base_angle})
                self.graph.add_edge("channel_change_max_%s_%d" % (w, channel_idx),
                                    "channel_move_max_%s_%d" % (w, channel_idx),
                                    label="move max %s" % w)

                self.graph.add_node("channel_ask_max_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Did the %s reach the shown position? Say yes or no." % w.replace("_", " "))
                self.graph.add_edge("channel_move_max_%s_%d" % (w, channel_idx), 
                                    "channel_ask_max_%s_%d" % (w, channel_idx),
                                    label="move ask confirmation max %d %s" % (channel_idx, w))

                self.graph.add_node("confirmation_moved_max_%s_%d" % (w, channel_idx), type="hear", 
                                    words='["yes", "no", "[unk]"]')
                self.graph.add_edge("channel_ask_max_%s_%d" % (w, channel_idx), 
                                    "confirmation_moved_max_%s_%d" % (w, channel_idx), 
                                    label="ask hear confirmation_%s_%d" % (w, channel_idx))
                
                self.graph.add_edge("confirmation_moved_max_%s_%d" % (w, channel_idx), 
                                    "channel_change_max_%s_%d" % (w, channel_idx),
                                    label="no")

                self.graph.add_node("update_max_%s_%d" % (w, channel_idx), type="update", 
                                    channel=channel_idx, motor=w, what="max")
                self.graph.add_edge("confirmation_moved_max_%s_%d" % (w, channel_idx), 
                                    "update_max_%s_%d" % (w, channel_idx),
                                    label="yes")

                # Calibrate minimum boundary
                self.graph.add_node("show_min_%s_%d" % (w, channel_idx), type="show", 
                                    image="%s_min.jpg" % w)
                self.graph.add_edge("update_max_%s_%d" % (w, channel_idx),
                                    "show_min_%s_%d" % (w, channel_idx),
                                    label="yes")

                self.graph.add_node("explain_min_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Excellent. Let us do the other side. I will move my motor until it reaches this position.")
                self.graph.add_edge("show_min_%s_%d" % (w, channel_idx), 
                                    "explain_min_%s_%d" % (w, channel_idx),
                                    label="explain min %s" % w)
                
                self.graph.add_node("channel_change_min_%s_%d" % (w, channel_idx), type="change", 
                                    what="angle", by=-10)
                self.graph.add_edge("explain_min_%s_%d" % (w, channel_idx),
                                    "channel_change_min_%s_%d" % (w, channel_idx),
                                    label="change min %s" % w)

                self.graph.add_node("channel_move_min_%s_%d" % (w, channel_idx), type="move", 
                                    motors={channel_idx: self.base_angle})
                self.graph.add_edge("channel_change_min_%s_%d" % (w, channel_idx),
                                    "channel_move_min_%s_%d" % (w, channel_idx),
                                    label="move min %s" % w)

                self.graph.add_node("channel_ask_min_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Did the %s reach the shown position? Say yes or no." % w.replace("_", " "))
                self.graph.add_edge("channel_move_min_%s_%d" % (w, channel_idx), 
                                    "channel_ask_min_%s_%d" % (w, channel_idx),
                                    label="move ask confirmation min %d %s" % (channel_idx, w))

                self.graph.add_node("confirmation_moved_min_%s_%d" % (w, channel_idx), type="hear", 
                                    words='["yes", "no", "[unk]"]')
                self.graph.add_edge("channel_ask_min_%s_%d" % (w, channel_idx), 
                                    "confirmation_moved_min_%s_%d" % (w, channel_idx), 
                                    label="ask hear confirmation_%s_%d" % (w, channel_idx))
                
                self.graph.add_edge("confirmation_moved_min_%s_%d" % (w, channel_idx), 
                                    "channel_change_min_%s_%d" % (w, channel_idx),
                                    label="no")

                self.graph.add_node("update_min_%s_%d" % (w, channel_idx), type="update", 
                                    channel=channel_idx, motor=w, what="min")
                self.graph.add_edge("confirmation_moved_min_%s_%d" % (w, channel_idx), 
                                    "update_min_%s_%d" % (w, channel_idx),
                                    label="yes")
                
                self.graph.add_node("stop_show_%s_%d" % (w, channel_idx), type="show", image=None)
                self.graph.add_edge("update_min_%s_%d" % (w, channel_idx), 
                                    "stop_show_%s_%d" % (w, channel_idx),
                                    label="stop show")

                self.graph.add_node("congratulate_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Excellent. We calibrated the %s motor together. Let us continue." % w.replace("_", " "))
                self.graph.add_edge("stop_show_%s_%d" % (w, channel_idx), 
                                    "congratulate_%s_%d" % (w, channel_idx),
                                    label="congratulate %s" % w)
                
                if channel_idx < 15:
                    self.graph.add_edge("congratulate_%s_%d" % (w, channel_idx),
                                        "channel_move_%d" % (channel_idx + 1),
                                        label="trying next one")
                else:
                    self.graph.add_edge("congratulate_%s_%d" % (w, channel_idx),
                                        "finished",
                                        label="tried last one")

        self.graph.add_node("finished", type="speak", text="That was an amazing effort. I am now calibrated.")
        self.graph.add_node("The End", type="end")
        self.graph.add_edge("finished", "The End", label="finished")

    def change(self, current_node, current_data, data_):
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]
        current_channel = int(current_node.split("_")[-1])
        change_what = current_data["what"]
        current_angle = self.graph.nodes[next_node]["motors"][current_channel]
        if change_what == "angle":
            self.graph.nodes[next_node]["motors"][current_channel] = current_angle + current_data["by"]
        return next_node

    def update(self, current_node, current_data, data_):
        self.data['motors'][current_data['motor']]['channel'] = current_data['channel']
        motor_name = "channel_move_%s_%s_%d" % (current_data['what'], current_data['motor'], current_data['channel'])
        current_channel = int(current_node.split("_")[-1])
        angle = self.graph.nodes[motor_name]['motors'][current_channel]
        self.data['motors'][current_data['motor']][current_data['what']] = angle
        if current_data['what'] == 'min':
            self.data['motors'][current_data['motor']]['calibrated'] = True
            # Compute neutral center position
            m_min = self.data['motors'][current_data['motor']].get('min', 200)
            m_max = self.data['motors'][current_data['motor']].get('max', 400)
            self.data['motors'][current_data['motor']]['center'] = (m_min + m_max) // 2

        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]
        logger.info(f"Updated {current_data['motor']} {current_data['what']} = {angle}")
        return next_node

    def done(self):
        import datetime
        print("\n[MotorCalibration] Calibration routine complete. Persisting parameters:")
        save_payload = dict(self.data["motors"])
        save_payload["system_calibrated"] = True
        save_payload["calibrated_at"] = datetime.datetime.now().isoformat()
        for k, v in save_payload.items():
            if isinstance(v, dict) and "channel" in v:
                v["calibrated"] = True
        print(json.dumps(save_payload, indent=4))
        saved_path = save_motor_calibration(save_payload)
        print(f"[MotorCalibration] SUCCESS: Saved local calibration to: {saved_path}")


def main(base_angle: int = 300, run_script: bool = True):
    print("=" * 60)
    print("      Gigi Interactive Motor Calibration Wizard")
    print("=" * 60)
    mcsg = MotorCalibration()
    mcsg.base_angle = base_angle
    mcsg.init_graph()
    mcsg.add_function("change", mcsg.change)
    mcsg.add_function("update", mcsg.update)
    mcsg.add_done()

    fuzzy = Character(activity=activity_name, gender='female')
    script = Script(graph=mcsg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    if run_script:
        print("[MotorCalibration] Running calibration session...")
        script.run()


if __name__ == "__main__":
    angle = 300
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        angle = int(sys.argv[1])
    main(base_angle=angle)