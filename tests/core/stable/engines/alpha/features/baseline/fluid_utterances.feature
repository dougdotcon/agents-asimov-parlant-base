Feature: Fluid Utterance
    Background:
        Given the alpha engine
        And an agent
        And that the agent uses the fluid_utterance message composition mode
        And an empty session

    Scenario: The agent greets the customer (fluid utterance)
        Given a guideline to greet with 'Howdy' when the session starts
        When processing is triggered
        Then a status event is emitted, acknowledging event -1
        And a status event is emitted, processing event -1
        And a status event is emitted, typing in response to event -1
        And a single message event is emitted
        And the message contains a 'Howdy' greeting
        And a status event is emitted, ready for further engagement after reacting to event -1

    Scenario: Adherence to guidelines without fabricating responses (fluid utterance)
        Given a guideline "account_related_questions" to respond to the best of your knowledge when customers inquire about their account
        And a customer message, "What's my account balance?"
        And that the "account_related_questions" guideline is matched with a priority of 10 because "Customer inquired about their account balance."
        And an utterance, "Sorry, I do not know"
        And an utterance, "Your account balance is {{balance}}"
        When messages are emitted
        Then the message contains the text "Sorry, I do not know"
        And the message doesn't contain the text "Your account balance is"

    Scenario: Responding based on data the user is providing (fluid utterance)
        Given a customer message, "I say that a banana is green, and an apple is purple. What did I say was the color of a banana?"
        And an utterance, "Sorry, I do not know"
        And an utterance, "The answer is {{generative.answer}}"
        When messages are emitted
        Then the message doesn't contain the text "I do not know"
        And the message mentions the color green
