"""
Compare Python implementation results to original Java results.
"""

import pandas as pd
import matplotlib.pyplot as plt
import os


def load_python_results(output_dir='output'):
    """Load Python model results."""
    spatial = pd.read_csv(f'{output_dir}/spatial_output.csv')

    try:
        seasonal = pd.read_csv(f'{output_dir}/agent_stats_by_season.csv')
    except:
        seasonal = None

    try:
        daily = pd.read_csv(f'{output_dir}/daily_calories.csv')
    except:
        daily = None

    return spatial, seasonal, daily


def analyze_results(spatial_df, seasonal_df, daily_df):
    """Analyze and visualize results."""

    print("\n" + "="*80)
    print("PYTHON MODEL RESULTS ANALYSIS")
    print("="*80)

    print(f"\nTotal agent-timesteps: {len(spatial_df)}")

    if seasonal_df is not None:
        print(f"\nCalorie Statistics:")
        print(f"  Mean total calories per agent-season: {seasonal_df['total_calories'].mean():.0f}")
        print(f"  Mean plant calories: {seasonal_df['plant_calories'].mean():.0f}")
        print(f"  Mean carcass calories: {seasonal_df['carcass_calories'].mean():.0f}")

        if seasonal_df['carcass_calories'].sum() > 0:
            ratio = seasonal_df['plant_calories'].sum() / seasonal_df['carcass_calories'].sum()
            print(f"  Plant:Meat ratio: {ratio:.2f}:1")

        # Plot results
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # By season
        season_totals = seasonal_df.groupby('season')['total_calories'].sum()
        axes[0,0].bar(season_totals.index, season_totals.values)
        axes[0,0].set_title('Total Calories by Season')
        axes[0,0].set_xlabel('Season')
        axes[0,0].set_ylabel('Calories')

        # Plant vs meat
        by_type = pd.DataFrame({
            'Plant': seasonal_df.groupby('season')['plant_calories'].sum(),
            'Meat': seasonal_df.groupby('season')['carcass_calories'].sum()
        })
        by_type.plot(kind='bar', ax=axes[0,1])
        axes[0,1].set_title('Plant vs Meat Calories by Season')
        axes[0,1].set_xlabel('Season')
        axes[0,1].set_ylabel('Calories')

        # Root vs non-root
        by_plant_type = pd.DataFrame({
            'Root': seasonal_df.groupby('season')['root_calories'].sum(),
            'Non-root': seasonal_df.groupby('season')['nonroot_calories'].sum()
        })
        by_plant_type.plot(kind='bar', ax=axes[1,0])
        axes[1,0].set_title('Root vs Non-root Plant Calories')
        axes[1,0].set_xlabel('Season')
        axes[1,0].set_ylabel('Calories')

        # By species
        by_species = seasonal_df.groupby('species')['total_calories'].sum()
        by_species.plot(kind='bar', ax=axes[1,1])
        axes[1,1].set_title('Total Calories by Species')
        axes[1,1].set_xlabel('Species')
        axes[1,1].set_ylabel('Calories')

        plt.tight_layout()
        plt.savefig('output/results_analysis.png')
        print("\n✓ Saved analysis plot to output/results_analysis.png")

    if daily_df is not None:
        # Create daily calorie plot
        fig, ax = plt.subplots(figsize=(14, 6))

        # Plot by species
        for species in daily_df['species'].unique():
            species_data = daily_df[daily_df['species'] == species]
            daily_avg = species_data.groupby('day')['total_calories'].mean()
            ax.plot(daily_avg.index, daily_avg.values, label=species, alpha=0.7)

        ax.set_title('Average Daily Calorie Intake by Species')
        ax.set_xlabel('Day')
        ax.set_ylabel('Calories')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('output/daily_calories_plot.png')
        print("✓ Saved daily calories plot to output/daily_calories_plot.png")


def compare_to_java(java_results_dir=None):
    """
    Compare to Java results if available.

    Args:
        java_results_dir: Path to directory with Java model output files
    """
    if java_results_dir is None:
        print("\nNo Java results provided for comparison")
        print("To compare, run Java model and provide results directory:")
        print("  compare_to_java(java_results_dir='/path/to/java/output')")
        return

    print("\n" + "="*80)
    print("COMPARING TO JAVA MODEL RESULTS")
    print("="*80)

    # Check if Java results exist
    if not os.path.exists(java_results_dir):
        print(f"✗ Java results directory not found: {java_results_dir}")
        return

    # Try to load Java results
    # Note: This is a placeholder - actual Java output format may vary
    java_files = os.listdir(java_results_dir)
    print(f"\nJava output files found: {len(java_files)}")
    for f in java_files[:10]:  # Show first 10
        print(f"  - {f}")

    # TODO: Implement detailed comparison logic based on Java output format
    print("\n⚠ Detailed comparison not yet implemented")
    print("Please manually compare output files:")
    print(f"  Python: ./output/")
    print(f"  Java:   {java_results_dir}")


def generate_summary_report(output_dir='output'):
    """Generate a comprehensive summary report."""

    print("\n" + "="*80)
    print("GENERATING SUMMARY REPORT")
    print("="*80)

    spatial, seasonal, daily = load_python_results(output_dir)

    report_lines = []
    report_lines.append("="*80)
    report_lines.append("HOMINIDS MODEL - SIMULATION SUMMARY REPORT")
    report_lines.append("="*80)
    report_lines.append("")

    # Basic statistics
    report_lines.append("BASIC STATISTICS")
    report_lines.append("-"*80)
    report_lines.append(f"Total agent-timesteps: {len(spatial)}")

    if seasonal is not None:
        n_agents = seasonal['agent_id'].nunique()
        n_seasons = seasonal['season'].nunique()
        report_lines.append(f"Number of agents: {n_agents}")
        report_lines.append(f"Number of seasons: {n_seasons}")
        report_lines.append("")

        # Calorie statistics
        report_lines.append("CALORIE STATISTICS (MEAN PER AGENT-SEASON)")
        report_lines.append("-"*80)
        report_lines.append(f"Total calories:    {seasonal['total_calories'].mean():>12.1f} kcal")
        report_lines.append(f"Plant calories:    {seasonal['plant_calories'].mean():>12.1f} kcal")
        report_lines.append(f"Carcass calories:  {seasonal['carcass_calories'].mean():>12.1f} kcal")
        report_lines.append(f"Root calories:     {seasonal['root_calories'].mean():>12.1f} kcal")
        report_lines.append(f"Non-root calories: {seasonal['nonroot_calories'].mean():>12.1f} kcal")
        report_lines.append("")

        # By species
        report_lines.append("CALORIES BY SPECIES")
        report_lines.append("-"*80)
        for species in seasonal['species'].unique():
            species_data = seasonal[seasonal['species'] == species]
            mean_total = species_data['total_calories'].mean()
            mean_plant = species_data['plant_calories'].mean()
            mean_carcass = species_data['carcass_calories'].mean()
            report_lines.append(f"{species}:")
            report_lines.append(f"  Total:   {mean_total:>10.1f} kcal/season")
            report_lines.append(f"  Plant:   {mean_plant:>10.1f} kcal/season")
            report_lines.append(f"  Carcass: {mean_carcass:>10.1f} kcal/season")
        report_lines.append("")

        # By season
        report_lines.append("CALORIES BY SEASON (ALL AGENTS)")
        report_lines.append("-"*80)
        for season in sorted(seasonal['season'].unique()):
            season_data = seasonal[seasonal['season'] == season]
            total = season_data['total_calories'].sum()
            plant = season_data['plant_calories'].sum()
            carcass = season_data['carcass_calories'].sum()
            report_lines.append(f"Season {season}:")
            report_lines.append(f"  Total:   {total:>12.1f} kcal")
            report_lines.append(f"  Plant:   {plant:>12.1f} kcal")
            report_lines.append(f"  Carcass: {carcass:>12.1f} kcal")
        report_lines.append("")

    # Write report to file
    report_file = os.path.join(output_dir, 'simulation_summary.txt')
    with open(report_file, 'w') as f:
        f.write('\n'.join(report_lines))

    # Also print to console
    print('\n'.join(report_lines))
    print(f"\n✓ Summary report saved to {report_file}")


if __name__ == '__main__':
    spatial, seasonal, daily = load_python_results()
    analyze_results(spatial, seasonal, daily)
    generate_summary_report()
    compare_to_java()
