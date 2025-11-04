class TestCommands:

    def test_search_sync_command(self, cli_runner):
        result = cli_runner.invoke(args=["search", "sync"])
        print(result.output)
        assert "Indexing..." in result.output
        assert " pages of datasets..." in result.output
