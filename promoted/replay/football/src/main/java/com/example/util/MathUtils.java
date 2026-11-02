package com.example.util;

public class MathUtils {
	public static double[] poissonDist(double lambda, int max) {
		double[] p = new double[max + 1];
		double e = Math.exp(-lambda);
		p[0] = e;
		for (int k = 1; k <= max; k++) {
			p[k] = p[k - 1] * lambda / k;
		}
		// normalize küçük hatalar için
		double sum = 0;
		for (double v : p)
			sum += v;
		if (Math.abs(sum - 1.0) > 1e-9) {
			for (int i = 0; i < p.length; i++)
				p[i] /= sum;
		}
		return p;
	}

	public static String fmtPct(double x) {
		return String.format("%.1f%%", x * 100.0);
	}

	/** 🔹 Sigmoid fonksiyonu (smooth thresholding için) */
	public static double sigmoid(double x) {
		return 1.0 / (1.0 + Math.exp(-x));
	}

	/**
	 * 🔹 Modified Bessel function of the first kind (Iₙ(x)) Skellam dağılımı için
	 * gerekir. Bu, düşük derecelerde (|x| < 50) oldukça stabildir.
	 */
	public static double besselI(int n, double x) {
		if (n < 0)
			n = -n; // I_{-n} = I_n

		// küçük x için seriye dayalı yaklaşım
		double sum = 0.0;
		double term = Math.pow(x / 2.0, n) / factorial(n);
		double k = 0.0;
		sum += term;

		while (term > 1e-12 * sum && k < 100) {
			k++;
			term *= Math.pow(x / 2.0, 2) / (k * (n + k));
			sum += term;
		}
		return sum;
	}

	public static double factorial(int n) {
		if (n <= 1)
			return 1.0;
		double res = 1.0;
		for (int i = 2; i <= n; i++)
			res *= i;
		return res;
	}
}
