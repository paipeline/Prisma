import argparse
from src.core.graph.codeReActLoop import CodeReActWorkflow


def cli():
    """
    Main command-line interface to run the prisma agent.
    -a means autonomous mode
    default is interactive mode
    usage:
    INTERACTIVE MODE: python -m src.core.prisma
    AUTONOMOUS MODE: python -m src.core.prisma -a
    """
    parser = argparse.ArgumentParser(description="Run the prisma agent.")
    parser.add_argument(
        "-a", "--autonomous", 
        action="store_true", 
        help="Run in autonomous mode (default: interactive mode)"
    )
    args, unknown = parser.parse_known_args()

    # The new CodeReActRunner handles the agent and tool setup.
    # The autonomous mode flag can be passed to the runner in the future.

    if args.autonomous:
        print("--- Starting prisma in AUTONOMOUS mode ---")
    else:
        print("--- Starting prisma in INTERACTIVE mode ---")

    runner = CodeReActWorkflow(interactive=not args.autonomous)

    print("Type 'exit' or 'quit' to end the conversation.")
    
    while True:
        user_input = input("\n> ")

        if user_input.lower() in ["exit", "quit"]:
            print("Ending conversation. Goodbye!")
            break

        # The runner handles the entire loop, including printing the final response.
        runner.run(user_input)

    # The environment info could be printed by the runner if needed.
    print("\nSession completed.")


if __name__ == "__main__":
    cli() 