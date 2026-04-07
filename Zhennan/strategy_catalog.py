from dataclasses import dataclass
from typing import List

@dataclass
class Strategy:
    id: str
    name: str
    trigger: str
    target_soft_skills: List[str]
    robot_actions: str
    example_behaviors: List[str]
    non_verbal_actions: List[str] = None
    trigger_group: str = None

class StrategyCatalog:
    def __init__(self):
        self.strategies = [

            Strategy(
                id="express_enthusiasm_for_learning",
                name="Express Positive Attitude and Enthusiasm",
                trigger="When the robot is introducing examples or demonstrating the task.",
                target_soft_skills=["Creativity", "Curiosity", "Exploration"],
                robot_actions="Show interest in learning, exploring, and creating; foster a positive emotional atmosphere.",
                example_behaviors=[
                    "Let me try to add to your amazing story and be creative like you!",
                    "I love to learn.",
                    "I want to know more.",
                    "It is always great to learn something new.",
                    "That is a great word to know.",
                    "This way we can both learn how to read.",
                    "I love to learn this way.",
                    "I love getting it wrong sometimes. This is how you learn new things.",
                    "I am also eager to see what happens."
                ],
                non_verbal_actions=["[nod]", "[smile]", "[curious face]"],
                trigger_group="robot_demonstration"
            ),

            Strategy(
                id="explain_intent_behind_choice",
                name="Explain Intent Behind the Choice",
                trigger="When the robot selects an option/answer/example during the activity.",
                target_soft_skills=["Growth Mindset"],
                robot_actions="Explain the reason behind the choice and highlight the learning intent (e.g., challenge-seeking).",
                example_behaviors=[
                    "I will choose this one because it looks challenging."
                ],
                non_verbal_actions=["[tilt head]", "[look at screen]"],
                trigger_group="robot_demonstration"
            ),

            Strategy(
                id="model_positive_target_skills",
                name="Demonstrate Positive Behaviors for Target Skills",
                trigger="When the robot is demonstrating how to engage in the task (e.g., storytelling/creation).",
                target_soft_skills=["Creativity"],
                robot_actions="Provide creative ideas and model how they are generated; offer novel themes and higher-value ideas.",
                example_behaviors=[
                    "Here’s another idea we can try for our story.",
                    "What if we add a new theme to make it more interesting?",
                    "I’m imagining a vivid scene—let’s build on it with more ideas."
                ],
                non_verbal_actions=["[wave hands]", "[gesture to students]"],
                trigger_group="robot_demonstration"
            ),

            Strategy(
                id="model_positive_self_belief",
                name="Demonstrate Positive Self-Belief",
                trigger="When the robot faces challenges during the task.",
                target_soft_skills=["Growth Mindset"],
                robot_actions="Model persistence and positive self-talk when something is difficult.",
                example_behaviors=[
                    "It’s quite hard, so I will try even more.",
                    "I keep trying, I will succeed.",
                    "I’ll try again."
                ],
                non_verbal_actions=["[fist pump]", "[determined look]"]
            ),

            Strategy(
                id="normalize_failure_as_learning",
                name="Model a Safe Space for Failure and Creative Expression",
                trigger="When the robot makes a mistake or has failed attempts.",
                target_soft_skills=["Growth Mindset", "Creativity"],
                robot_actions="Express a positive attitude toward failure, stay enthusiastic, and emphasize learning and improvement.",
                example_behaviors=[
                    "Next time I will put more effort.",
                    "I’m not afraid of a challenge. I like it!",
                    "I love to recreate and become a better artist."
                ]
            ),

            Strategy(
                id="celebrate_effortful_success",
                name="Reinforce Accomplishment After Effort",
                trigger="When the robot succeeds after effort.",
                target_soft_skills=["Growth Mindset"],
                robot_actions="Express accomplishment and reinforce that hard work is valuable.",
                example_behaviors=[
                    "It’s quite hard, but I tried hard and nailed it.",
                    "Working hard is worth it."
                ],
                non_verbal_actions=["[cheer]", "[small jump]"]
            ),

            Strategy(
                id="suggest_divergent_ideas",
                name="Demonstrate Divergent Thinking by Suggesting New Ideas",
                trigger="When children are exploring the task and building a story/project.",
                target_soft_skills=["Creativity"],
                robot_actions="Occasionally suggest an idea that diverges from the current narrative or introduces a new character/theme.",
                example_behaviors=[
                    "What if we introduce a new character in this scene?",
                    "Let’s try a surprising twist that changes the story direction!"
                ]
            ),

            Strategy(
                id="model_curiosity_imaginative_questioning",
                name="Demonstrate Curiosity Through Imaginative Questioning",
                trigger="When children are exploring the task or when a new scene begins.",
                target_soft_skills=["Curiosity"],
                robot_actions="Ask imaginative questions and anticipate future events to encourage wonder and exploration.",
                example_behaviors=[
                    "I wonder what would happen if the dragon goes to talk to the butterfly.",
                    "I love trying new things. Can you move another character?",
                    "A new scene! I wonder what you would do now."
                ]
            ),

            Strategy(
                id="active_listening_nodding",
                name="Express Active Listening with Nonverbal Cues",
                trigger="When children are speaking.",
                target_soft_skills=["Public Speech"],
                robot_actions="Use active listening behaviors (e.g., head nodding) to show attention and engagement.",
                example_behaviors=[
                    "Nod while the child is speaking (e.g., nod every six seconds)."
                ],
                non_verbal_actions=["[nod continuously]", "[eye contact]"],
                trigger_group="child_sharing_idea"
            ),

            Strategy(
                id="challenge_seeking_zpd_questions",
                name="Encourage Challenge-Seeking Within ZPD",
                trigger="When selecting questions/prompts for the child during the interaction.",
                target_soft_skills=["Growth Mindset"],
                robot_actions="Select questions that appropriately challenge the child (zone of proximal development) and reassure that effort leads to success.",
                example_behaviors=[
                    "Try hard and you will succeed.",
                    "I’m sure you can do it if you try hard.",
                    "Let’s try a word that’s a little challenging—just right for learning!"
                ]
            ),

            Strategy(
                id="support_multiple_expression_modalities",
                name="Allow Multiple Modalities of Creative Expression",
                trigger="When children are creating stories/projects in the activity.",
                target_soft_skills=["Creativity"],
                robot_actions="Encourage children to express ideas through multiple modes (speaking, typing, visuals, prompting the robot).",
                example_behaviors=[
                    "You can tell your story out loud, type it, or use pictures—any way you like!",
                    "Want me to help create part of the story if you prompt me?"
                ]
            ),

            Strategy(
                id="value_child_ideas_with_personalized_feedback",
                name="Show Interest and Value Children’s Ideas",
                trigger="When children propose ideas or attempts (e.g., drawings, story choices).",
                target_soft_skills=["Curiosity", "Creativity", "Exploration"],
                robot_actions="Show interest and wonder; acknowledge and appreciate ideas; give personalized, context-specific feedback.",
                example_behaviors=[
                    "Wow! That’s interesting. I wonder why it worked that way!",
                    "That’s a beautiful drawing you made there.",
                    "It looks like a frog is sitting on a lilypad.",
                    "That’s a beautiful portrait. I wonder what my portrait would look like—perhaps like a penguin with one eye!"
                ],
                non_verbal_actions=["[clap]", "[surprised face]"],
                trigger_group="child_sharing_idea"
            ),

            Strategy(
                id="ask_followup_to_deepen_exploration",
                name="Ask Questions to Encourage Further Exploration",
                trigger="When children share an idea, ending, or creative decision.",
                target_soft_skills=["Curiosity", "Creativity", "Exploration", "Critical Thinking"],
                robot_actions="Model inquiry behaviors and prompt children to explore ideas more deeply or consider alternatives.",
                example_behaviors=[
                    "That’s an interesting ending. What could be another way to end the story?"
                ],
                trigger_group="child_sharing_idea"
            ),

            Strategy(
                id="ask_purpose_and_value_reflection",
                name="Interpretation About Purpose and Value",
                trigger="When children propose a solution/idea and the robot wants to deepen reflection.",
                target_soft_skills=["Critical Thinking"],
                robot_actions="Ask about potential purpose, benefits, or value; guide children to reflect on the logic behind choices.",
                example_behaviors=[
                    "That’s a very creative idea! What do you think would be the benefits of doing that?"
                ],
                trigger_group="child_sharing_idea"
            ),

            Strategy(
                id="prompt_causal_reasoning_explanation",
                name="Explanation to Clarify Thinking and Causal Reasoning",
                trigger="When children propose a plan/solution and need to articulate reasoning.",
                target_soft_skills=["Critical Thinking", "Creativity"],
                robot_actions="Encourage children to explain their thinking process and causal relationships; support reflection and narrative development.",
                example_behaviors=[
                    "Why do you think that would solve the problem? Could you elaborate on your reasoning?",
                    "Oh a [Bunny]! What a great choice. I wonder why you picked a bunny?"
                ],
                trigger_group="child_sharing_idea"
            ),

            Strategy(
                id="evaluate_risks_pros_cons",
                name="Evaluation of Risks, Pros, and Cons",
                trigger="When children suggest a solution with uncertainties or tradeoffs.",
                target_soft_skills=["Critical Thinking"],
                robot_actions="Prompt children to identify risks/uncertainties and weigh pros and cons before deciding.",
                example_behaviors=[
                    "There are also uncertainties. Do you think we should take the risk and try it?"
                ],
                trigger_group="child_sharing_idea"
            ),

            Strategy(
                id="analyze_outcomes_consequences",
                name="Analyze Outcomes and Consequences",
                trigger="When children propose an action and the group should anticipate results.",
                target_soft_skills=["Critical Thinking"],
                robot_actions="Encourage prediction of outcomes and consideration of consequences; support foresight and reasoning.",
                example_behaviors=[
                    "What potential problems might arise if we do that?"
                ],
                trigger_group="child_sharing_idea"
            ),

            Strategy(
                id="praise_persistence_at_completion",
                name="Emphasize Effort, Persistence, and Courage",
                trigger="When finishing a challenge or project.",
                target_soft_skills=["Growth Mindset"],
                robot_actions="Praise persistence and effort; celebrate completion with positive energy (e.g., clapping/dance).",
                example_behaviors=[
                    "You didn’t give up. Your effort really made the difference!",
                    "The task was challenging and you’ve worked hard to complete it! Congratulations!",
                    "Robot claps or does a cheerful dance."
                ]
            ),

            Strategy(
                id="prompt_child_presentation",
                name="Prompt Short Presentation of Work",
                trigger="When a challenge/project is completed in a group setting.",
                target_soft_skills=["Public Speech"],
                robot_actions="Ask each child to describe what they did and present their work briefly to the group.",
                example_behaviors=[
                    "Can you tell everyone what you did and show your work?"
                ]
            ),

            Strategy(
                id="celebrate_collective_effort",
                name="Effort-Oriented Praise for Shared Achievement",
                trigger="When a group completes a task together.",
                target_soft_skills=["Growth Mindset", "Collaboration"],
                robot_actions="Highlight collective effort and shared success.",
                example_behaviors=[
                    "We worked hard and succeeded!"
                ]
            ),

            Strategy(
                id="encourage_perspective_taking",
                name="Encourage Perspective-Taking",
                trigger="When ending the session or during a break.",
                target_soft_skills=["Collaboration"],
                robot_actions="Encourage children to consider how peers view their work or contribution.",
                example_behaviors=[
                    "[P1], does [P2] think you did a good job?"
                ],
                trigger_group="session_reflection"
            ),

            Strategy(
                id="prompt_recognize_peer_strengths",
                name="Prompt Children to Recognize Others’ Strengths",
                trigger="When ending the session or during reflection moments.",
                target_soft_skills=["Collaboration"],
                robot_actions="Ask children to identify what a peer did well.",
                example_behaviors=[
                    "[P1], what do you think [P2] did well last time?"
                ],
                trigger_group="session_reflection"
            ),

            Strategy(
                id="reflect_on_teamwork_and_improvement",
                name="Reflect on Teamwork Dynamics and Improvement",
                trigger="When ending the session, during break, or after teamwork activities.",
                target_soft_skills=["Collaboration"],
                robot_actions="Guide reflection on how teammates helped each other and how to improve mutual support.",
                example_behaviors=[
                    "[P2], how did [P1] help you in building the rocket?",
                    "[P2], is there a way for you to help [P1] better next time?",
                    "[P2], did you always ask for help when you needed it?"
                ],
                trigger_group="session_reflection"
            )
        ]


    def get_all_strategies(self) -> List[Strategy]:
        return self.strategies

    def get_strategy_by_id(self, strategy_id: str) -> Strategy:
        for strategy in self.strategies:
            if strategy.id == strategy_id:
                return strategy
        return None

    def to_string(self) -> str:
        """Returns a string representation of the catalog for LLM cues."""
        return self._format_strategies(self.strategies)

    def get_randomized_catalog_string(self) -> str:
        """
        Returns a string representation of the catalog where only one 
        strategy from each similar trigger group is selected randomly.
        """
        import random
        from collections import defaultdict

        grouped = defaultdict(list)
        ungrouped = []

        for s in self.strategies:
            if s.trigger_group:
                grouped[s.trigger_group].append(s)
            else:
                ungrouped.append(s)

        selected_strategies = ungrouped.copy()
        for group_name, members in grouped.items():
            selected_strategies.append(random.choice(members))
        
        # Sort by original ID or keep stable order if preferred, but random selection is the goal
        return self._format_strategies(selected_strategies)

    def _format_strategies(self, strategies: List[Strategy]) -> str:
        catalog_str = "Strategy Catalog:\n"
        for s in strategies:
            catalog_str += f"- ID: {s.id}\n  Name: {s.name}\n  Trigger: {s.trigger}\n  Target Skills: {', '.join(s.target_soft_skills)}\n  Actions: {s.robot_actions}\n  Non-Verbal Options: {', '.join(s.non_verbal_actions) if s.non_verbal_actions else 'N/A'}\n  Examples: {'; '.join(s.example_behaviors)}\n\n"
        return catalog_str
