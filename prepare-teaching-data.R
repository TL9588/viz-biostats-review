# Build the small teaching datasets used by the data visualization tutorials.
#
# This script is run MANUALLY and never during a documentation build. It
# exports two datasets that ship inside R packages to plain CSV files, so that
# the R and Python tutorials read identical files and report identical numbers.
#
# Requires the project environment, which provides palmerpenguins and MASS.
#
# Usage, from the repository root:
#
#     Rscript utils/data/prepare-teaching-data.R

output_directories <- c(
  file.path("source", "viz", "r", "data"),
  file.path("source", "viz", "python", "data")
)

write_everywhere <- function(data, filename) {
  for (directory in output_directories) {
    dir.create(directory, recursive = TRUE, showWarnings = FALSE)
    path <- file.path(directory, filename)
    write.csv(data, path, row.names = FALSE, na = "")
    message(sprintf("  wrote %s (%d rows)", path, nrow(data)))
  }
}

# Palmer Penguins, released under a Creative Commons Zero licence. Column
# names are already readable and are kept as published.
penguins <- as.data.frame(palmerpenguins::penguins)
write_everywhere(penguins, "penguins.csv")

# Low birth weight study. The published column names are abbreviations, so
# they are expanded here and the coded factors given their labels.
birthwt <- MASS::birthwt
birthwt <- data.frame(
  low_birth_weight = factor(
    ifelse(birthwt$low == 1, "Yes", "No"),
    levels = c("No", "Yes")
  ),
  birth_weight_g = birthwt$bwt,
  mother_age_years = birthwt$age,
  mother_weight_lb = birthwt$lwt,
  race = factor(
    birthwt$race,
    levels = c(1, 2, 3),
    labels = c("White", "Black", "Other")
  ),
  smoker = factor(
    ifelse(birthwt$smoke == 1, "Yes", "No"),
    levels = c("No", "Yes")
  ),
  previous_preterm = birthwt$ptl,
  hypertension = factor(
    ifelse(birthwt$ht == 1, "Yes", "No"),
    levels = c("No", "Yes")
  ),
  uterine_irritability = factor(
    ifelse(birthwt$ui == 1, "Yes", "No"),
    levels = c("No", "Yes")
  ),
  first_trimester_visits = birthwt$ftv
)
write_everywhere(birthwt, "birthwt.csv")

message("\nDone.")
