const path = require('path');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const rtlcss = require('rtlcss');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const HandlebarsPlugin = require('handlebars-webpack-plugin');
const fs = require('fs-extra');
const { RawSource } = require('webpack-sources');
const BrowserSyncPlugin = require('browser-sync-webpack-plugin')


// define global paths
const folder = {
    src: "./src/",
    src_assets: "./src/assets/",
    dist: "./static/",
    dist_assets: "./static/assets/"
};

// define rtl css pairs
const cssPairs = [
    { ltr: 'css/app.min.css', rtl: 'css/app-rtl.min.css' },
    { ltr: 'css/bootstrap.min.css', rtl: 'css/bootstrap-rtl.min.css' },
    // Add more pairs as needed
];

module.exports = {
    mode: 'development', // or 'production'
    entry: {
        app: path.join(__dirname, folder.src_assets, 'scss/app.scss'),
        bootstrap: path.join(__dirname, folder.src_assets, 'scss/bootstrap.scss'),
        icons: path.join(__dirname, folder.src_assets, 'scss/icons.scss'),
    },
    output: {
        path: path.resolve(__dirname, folder.dist_assets),
        filename: 'chunk/[name].js',
    },
    performance: {
        hints: false, // Disable performance hints
    },
    devServer: {
        static: {
            directory: path.join(__dirname, folder.dist),
            serveIndex: true,
        },
        hot: "only",
    },
    module: {
        rules: [
            {
                test: /\.scss$/,
                use: [
                    MiniCssExtractPlugin.loader,
                    'css-loader',
                    'sass-loader',
                ],
            },
            {
                test: /\.html$/,
                use: 'html-loader',
            },
        ],
    },
    plugins: [
        new MiniCssExtractPlugin({
            filename: 'css/[name].min.css',
        }),
        new CopyWebpackPlugin({
            patterns: [
                { from: path.join(__dirname, folder.src_assets, 'images'), to: path.join(__dirname, folder.dist_assets, 'images') },
                { from: path.join(__dirname, folder.src_assets, 'js'), to: path.join(__dirname, folder.dist_assets, 'js') },
                { from: path.join(__dirname, folder.src_assets, 'libs'), to: path.join(__dirname, folder.dist_assets, 'libs') },
                { from: path.join(__dirname, folder.src_assets, 'libs'), to: path.join(__dirname, folder.dist_assets, 'libs') },
            ],
        }),
        new BrowserSyncPlugin({
            // browse to http://localhost:3000/ during development,
            // ./public directory is being served
            host: 'localhost',
            port: 3000,
            server: { baseDir: [folder.dist] }
        }),
        {
            apply(compiler) {
                compiler.hooks.thisCompilation.tap('GenerateRTL', (compilation) => {
                    compilation.hooks.processAssets.tap(
                        {
                            name: 'GenerateRTL',
                            stage: compilation.PROCESS_ASSETS_STAGE_ADDITIONAL,
                        },
                        () => {
                            cssPairs.forEach((pair) => {
                                const ltrCss = compilation.assets[pair.ltr].source(); // Use compilation.assets to retrieve the asset
                                const rtlCss = rtlcss.process(ltrCss, { autoRename: false, clean: false });
                                compilation.emitAsset(pair.rtl, new RawSource(rtlCss)); // Use emitAsset to add the asset
                            });
                        }
                    );
                });
            },
        },
    ],
};

