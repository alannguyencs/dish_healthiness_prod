import React from "react";

// Import hand images
import fistImage from "../assets/images/hand/fist.png";
import cuppedHandImage from "../assets/images/hand/a_cupped_hand.png";
import palmImage from "../assets/images/hand/the_palm.png";
import thumbnailImage from "../assets/images/hand/the_thumbnail.png";
import tipOfThumbImage from "../assets/images/hand/tip_of_thumb.png";

const ServingSizeReference = () => {
  const standardMeasurements = [
    { unit: "1 cup", metric: "240 mL" },
    { unit: "1/2 cup", metric: "120 mL" },
    { unit: "3/4 cup", metric: "180 mL" },
    { unit: "1 tablespoon (tbsp)", metric: "15 mL" },
    { unit: "1 teaspoon (tsp)", metric: "5 mL" },
    { unit: "1 fluid ounce", metric: "30 mL" },
    { unit: "1 ounce (weight)", metric: "28 g" },
  ];

  const handIllustrations = [
    {
      gesture: "Fist (closed)",
      equivalent: "1 cup (240 mL)",
      image: fistImage,
    },
    {
      gesture: "Cupped hand",
      equivalent: "1/2 cup (120 mL)",
      image: cuppedHandImage,
    },
    {
      gesture: "Palm (no fingers)",
      equivalent: "2-3 oz meat (56-84 g)",
      image: palmImage,
    },
    {
      gesture: "Thumb (whole)",
      equivalent: "1 tbsp (15 mL)",
      image: thumbnailImage,
    },
    {
      gesture: "Thumb tip",
      equivalent: "1 tsp (5 mL)",
      image: tipOfThumbImage,
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-xl font-semibold text-gray-800">
            Serving Size Reference Guide
          </h1>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-8">
        {/* Official FDA definition section */}
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            What is a "serving size"? — Official FDA definition
          </h2>

          <p className="text-gray-700 mb-4">
            Under U.S. nutrition-labeling rules (21 CFR 101.9(b)), the{" "}
            <strong>serving size</strong> on a Nutrition Facts label is the
            amount of that food{" "}
            <strong>customarily consumed per eating occasion</strong> by people
            4 years of age or older. It is <em>not</em> a recommendation of how
            much to eat — it is a fixed reference amount so the calories,
            protein, and other numbers on the label are calculated on a
            consistent basis across brands.
          </p>

          <p className="text-gray-700 mb-4">
            Serving sizes are derived from the{" "}
            <strong>Reference Amounts Customarily Consumed</strong> (RACC) table
            in 21 CFR 101.12(b), which sets a standard reference amount per food
            category based on national food-consumption surveys. Each serving
            size must be expressed in both a{" "}
            <strong>common household measure</strong> (cup, tablespoon, slice,
            piece, fluid ounce, ounce) and its{" "}
            <strong>metric equivalent</strong> (grams or milliliters) — e.g.{" "}
            <code className="bg-gray-100 px-1 rounded">1 cup (240 mL)</code>.
            For packages that a single person would{" "}
            <strong>reasonably consume at one eating occasion</strong> (e.g. a
            20 fl oz soda bottle), the whole container counts as one serving,
            not the RACC.
          </p>

          <p className="text-gray-700 mb-4">
            The FDA's{" "}
            <em>
              Guidance for Industry — Guidelines for Determining Metric
              Equivalents of Household Measures
            </em>{" "}
            provides the rounded metric equivalents manufacturers use when
            printing the household-measure portion of the label (1 cup = 240 mL,
            1 tbsp = 15 mL, 1 tsp = 5 mL, etc.). Those equivalents are the same
            values in the Standard Measurements table below.
          </p>

          <div className="mt-4 border-t border-gray-200 pt-4">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
              Sources
            </h3>
            <ul className="space-y-1 text-sm">
              <li>
                <a
                  href="https://www.fda.gov/regulatory-information/search-fda-guidance-documents/guidance-industry-guidelines-determining-metric-equivalents-household-measures"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700 underline"
                >
                  FDA — Guidance for Industry: Guidelines for Determining Metric
                  Equivalents of Household Measures
                </a>
              </li>
              <li>
                <a
                  href="https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/subpart-A/section-101.9"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700 underline"
                >
                  21 CFR 101.9(b) — Nutrition labeling of food (serving size
                  definition)
                </a>
              </li>
              <li>
                <a
                  href="https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/subpart-A/section-101.12"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700 underline"
                >
                  21 CFR 101.12(b) — Reference Amounts Customarily Consumed
                  (RACC) per eating occasion
                </a>
              </li>
              <li>
                <a
                  href="https://www.fda.gov/food/nutrition-facts-label/serving-size-nutrition-facts-label"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700 underline"
                >
                  FDA — Serving Size on the Nutrition Facts Label (consumer
                  overview)
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Standard Measurements Section */}
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Standard Measurements (FDA/USDA)
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">
                    Unit
                  </th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">
                    Metric Equivalent
                  </th>
                </tr>
              </thead>
              <tbody>
                {standardMeasurements.map((item, index) => (
                  <tr
                    key={index}
                    className={index % 2 === 0 ? "bg-gray-50" : "bg-white"}
                  >
                    <td className="py-3 px-4 text-gray-800 font-medium">
                      {item.unit}
                    </td>
                    <td className="py-3 px-4 text-gray-600">{item.metric}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Hand Illustrations Section */}
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Hand Size Reference
          </h2>
          <p className="text-gray-600 text-sm mb-6">
            Use your hand as a quick reference to estimate serving sizes without
            measuring tools.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {handIllustrations.map((item, index) => (
              <div
                key={index}
                className="border border-gray-200 rounded-lg p-4 flex flex-col items-center text-center hover:shadow-md transition-shadow"
              >
                <div className="w-24 h-24 mb-3 flex items-center justify-center">
                  <img
                    src={item.image}
                    alt={item.gesture}
                    className="max-w-full max-h-full object-contain"
                  />
                </div>
                <h3 className="font-semibold text-gray-800 mb-1">
                  {item.gesture}
                </h3>
                <p className="text-sm text-blue-600 font-medium">
                  {item.equivalent}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Tips Section */}
        <div className="bg-blue-50 rounded-lg p-6 border border-blue-200">
          <h2 className="text-lg font-semibold text-blue-800 mb-3">
            Quick Tips
          </h2>
          <ul className="space-y-2 text-blue-700 text-sm">
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">&#8226;</span>
              <span>
                <strong>cup</strong> - Best for liquids, grains, vegetables, and
                salads
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">&#8226;</span>
              <span>
                <strong>oz</strong> - Best for meats, cheeses, and solid foods
                by weight
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">&#8226;</span>
              <span>
                <strong>slice</strong> - Best for bread, pizza, cake, and pie
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">&#8226;</span>
              <span>
                <strong>tablespoon</strong> - Best for sauces, dressings, and
                spreads
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-500 mt-0.5">&#8226;</span>
              <span>
                <strong>teaspoon</strong> - Best for oils, seasonings, and small
                condiment amounts
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default ServingSizeReference;
