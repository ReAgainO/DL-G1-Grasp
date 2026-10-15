"""Reuse the audited generator; enforce this wave's four CPU threads."""
import generator_base as generator
generator.torch.set_num_threads(4)
generator.main()
