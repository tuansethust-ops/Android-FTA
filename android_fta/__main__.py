"""Allow running as `python -m android_fta`."""

from __future__ import annotations

import sys

from android_fta.cli.commands import cmd_compare, cmd_run, setup_logging
from android_fta.cli.parser import create_parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    setup_logging(verbose=args.verbose, quiet=args.quiet)

    if args.command == "run":
        return cmd_run(
            skill=args.skill,
            trace=args.trace,
            output=args.output,
            format=args.format,
            max_workers=args.max_workers,
        )
    elif args.command == "compare":
        return cmd_compare(
            dut=args.dut,
            ref=args.ref,
            skill=args.skill,
            output=args.output,
            parser_regex=args.parser_regex,
            format=args.format,
            max_workers=args.max_workers,
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
