# Ureal Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Hassfest Validation](https://github.com/guiguihao/ureal_home/actions/workflows/hassfest.yml/badge.svg)](https://github.com/guiguihao/ureal_home/actions/workflows/hassfest.yml)
[![HACS Validation](https://github.com/guiguihao/ureal_home/actions/workflows/hacs.yml/badge.svg)](https://github.com/guiguihao/ureal_home/actions/workflows/hacs.yml)

Ureal Home Assistant 集成（`ureal_home`）是专门为接入 [悠瑞智能 (hzureal.com)](https://www.hzureal.com/) 设备的 Home Assistant 自定义组件。该集成利用云端 API，能够自动发现并同步您账号下的网关和子设备，并将其作为实体接入 Home Assistant 进行状态监控与联动控制。

---

## 🌟 特性

* 🔐 **便捷配置**：支持使用手机号、密码直接在 Home Assistant 的 UI 界面中登录并配置。
* 🏠 **多维度分组**：根据云端接口自动同步“区域”和“房间”，在 Home Assistant 中自动分组和分配设备。
* ⚡ **多平台实体支持**：
  * **传感器 (Sensor)**：自动上报温度、电流、功率、模式、状态等各种数据（自动过滤重叠的反馈属性）。
  * **开关 (Switch)**：支持单通道和多通道物理开关或灯光开关控制。
  * **数值调节 (Number)**：支持空调/地暖开关温差、水泵延时启动等精细参数设定。
  * **模式选择 (Select)**：支持采暖流量计类型、系统模式等选择控制。
* 🔄 **智能状态同步**：基于 `DataUpdateCoordinator` 数据更新器，本地状态乐观更新防止 UI 按钮“回跳”，多层级延时轮询保障体验。

---

## 📦 安装方法

### 方法一：通过 HACS 商店安装（推荐）

1. 确保您的 Home Assistant 已安装 **HACS**（Home Assistant Community Store）。
2. 在 HACS 中搜索 `Ureal Home`。
3. 点击 **Download** 安装。
4. 重启 Home Assistant。

*(如果是自定义存储库状态下，请打开 HACS -> 右上角三个点 -> 自定义存储库，添加 `https://github.com/guiguihao/ureal_home` 并选择类型为 `Integration`。)*

### 方法二：手动安装

1. 下载此仓库的 ZIP 压缩包。
2. 解压后，将 `custom_components/ureal_home` 文件夹复制到您 Home Assistant 配置目录的 `custom_components/` 下。
3. 复制后的结构应为：
   ```text
   config/
   └── custom_components/
       └── ureal_home/
           ├── __init__.py
           ├── manifest.json
           └── ...
   ```
4. 重启 Home Assistant。

---

## ⚙️ 配置与使用

1. 登录 Home Assistant 后，进入 **设置** -> **设备与服务**。
2. 点击右下角 **添加集成**。
3. 搜索并选择 **Ureal Home**。
4. 输入您的优瑞云账号信息：
   * **用户名/手机号**
   * **密码**
   * **服务器地址**（默认为官方云端接口，测试环境可自定义修改）
5. 点击提交，集成将自动检索所有绑定的网关与末端子设备，并在 HA 中创建对应的实体。

---

## 🛠️ 支持的设备类型与过滤规则

本集成支持自动读取优瑞智能的主流网关与子设备。为了避免实体冗余：
1. **自动过滤**：对于型号第二位是 `AC`（空调）、`FH`（地暖）、`NTC`（温度传感器）、`ZTC` 的设备，集成了自动的过滤排除逻辑，以确保界面只展示控制实体，避免重复生成传感器。
2. **传感器合并**：自动剔除已用作开关 (Switch)、数值调整 (Number)、下拉选择 (Select) 的反馈节点，防止产生重复的数值传感器。

---

## 🤝 参与贡献

如果您在使用中发现 BUG，或有新的设备控制需求：
1. 请在此仓库提交 [Issue](https://github.com/guiguihao/ureal_home/issues)。
2. 欢迎直接提交 [Pull Request](https://github.com/guiguihao/ureal_home/pulls) 帮助完善本项目。

---

## 📄 开源协议

本项目采用 **MIT** 协议开源，详情请参阅 [LICENSE](LICENSE) 文件。
